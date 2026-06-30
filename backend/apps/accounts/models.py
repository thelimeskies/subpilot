"""Account-domain models.

Per docs/technical/django-model-contracts.md and the synthesis plan:

- :class:`User` - extends AbstractUser; email is the username; adds MFA, email-
  verification, and onboarding fields. Password is hashed with Argon2 (see
  ``settings.PASSWORD_HASHERS``).
- :class:`Merchant` - the tenant root. ``slug`` and ``id`` are unique.
- :class:`Environment` - per-merchant ``test``/``live`` configuration. Holds
  Nomba processor credentials (encrypted at rest via ``apps.common.crypto``).
- :class:`TeamMember` - membership of a User in a Merchant with a ``Role``.
- :class:`ApiKey` - hashed (sha256) public-API credentials, scoped to one
  merchant + environment.
- :class:`EmailVerificationToken`, :class:`PasswordResetToken`,
  :class:`MfaChallenge` - short-lived tokens for the FE auth flow.

Internal roles map to the FE's smaller role enum at the response layer
(see ``apps.accounts.serializers.role_to_frontend``):

    Owner          -> "Owner"
    Billing Admin  -> "Admin"
    Developer      -> "Admin"          (FE has no Developer; closest is Admin)
    Finance        -> "Finance"
    Support        -> "Support"
    Analyst        -> "Read-only"
    Platform Op    -> (does not appear on merchant dashboard)
"""
from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.crypto import decrypt, encrypt, hash_secret
from apps.common.models import BaseDomainModel


class Role(models.TextChoices):
    """Internal roles per docs/product/rbac-permissions-matrix.md."""

    OWNER = "owner", _("Owner")
    BILLING_ADMIN = "billing_admin", _("Billing Admin")
    DEVELOPER = "developer", _("Developer")
    FINANCE = "finance", _("Finance")
    SUPPORT = "support", _("Support")
    ANALYST = "analyst", _("Analyst")
    PLATFORM_OPERATOR = "platform_operator", _("Platform Operator")


# Mapping internal role -> FE-visible role on the dashboard.
INTERNAL_ROLE_TO_FE = {
    Role.OWNER: "Owner",
    Role.BILLING_ADMIN: "Admin",
    Role.DEVELOPER: "Admin",
    Role.FINANCE: "Finance",
    Role.SUPPORT: "Support",
    Role.ANALYST: "Read-only",
}


class UserManager(BaseUserManager):
    """Email-as-username manager."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        # AbstractUser still has a non-null `username`; we derive it from email.
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """SubPilot user. ``email`` is unique and used as the login identifier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Email is the canonical identifier.
    email = models.EmailField(_("email address"), unique=True, db_index=True)

    # Optional display name (separate from first/last so we can preserve the
    # user's full original name from sign-up without splitting heuristics).
    display_name = models.CharField(max_length=128, blank=True, default="")

    # Auth state.
    email_verified = models.BooleanField(default=False)
    onboarding_complete = models.BooleanField(default=False)

    # MFA. ``mfa_secret`` stores the Fernet-encrypted base32 TOTP seed so
    # rest-at-rest exposure does not leak active TOTP secrets.
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(max_length=512, blank=True, default="")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self) -> str:  # pragma: no cover
        return self.email

    # --- Convenience accessors ---------------------------------------------------
    @property
    def mfa_secret(self) -> str:
        return decrypt(self.mfa_secret_encrypted)

    @mfa_secret.setter
    def mfa_secret(self, value: str) -> None:
        self.mfa_secret_encrypted = encrypt(value) if value else ""

    @property
    def initials(self) -> str:
        source = self.display_name or self.get_full_name() or self.email
        parts = [p for p in source.replace("@", " ").split() if p]
        if not parts:
            return "U"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


class Merchant(BaseDomainModel):
    """Top-level tenant. Holds product/billing state for a workspace."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")
        CLOSED = "closed", _("Closed")

    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    default_currency = models.CharField(max_length=3, default="NGN")
    industry = models.CharField(max_length=64, blank=True, default="")
    nomba_account_id = models.CharField(max_length=128, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "accounts_merchant"

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class Environment(BaseDomainModel):
    """Per-merchant ``test``/``live`` configuration."""

    class Mode(models.TextChoices):
        TEST = "test", _("Test")
        LIVE = "live", _("Live")

    class NombaIntegrationMode(models.TextChoices):
        PLATFORM = "platform", _("Platform-managed")
        BYOK = "byok", _("Bring your own Nomba keys")

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="environments")
    mode = models.CharField(max_length=8, choices=Mode.choices)
    nomba_integration_mode = models.CharField(
        max_length=16,
        choices=NombaIntegrationMode.choices,
        default=NombaIntegrationMode.PLATFORM,
    )
    nomba_account_id = models.CharField(max_length=128, blank=True, default="")
    nomba_client_id = models.CharField(max_length=128, blank=True, default="")
    nomba_client_secret_encrypted = models.CharField(max_length=512, blank=True, default="")
    webhook_secret_encrypted = models.CharField(max_length=512, blank=True, default="")
    publishable_key = models.CharField(max_length=80, blank=True, default="", db_index=True)

    class Meta:
        db_table = "accounts_environment"
        constraints = [
            models.UniqueConstraint(fields=["merchant", "mode"], name="uniq_merchant_environment_mode"),
        ]

    @property
    def nomba_client_secret(self) -> str:
        return decrypt(self.nomba_client_secret_encrypted)

    @nomba_client_secret.setter
    def nomba_client_secret(self, value: str) -> None:
        self.nomba_client_secret_encrypted = encrypt(value) if value else ""

    @property
    def webhook_secret(self) -> str:
        return decrypt(self.webhook_secret_encrypted)

    @webhook_secret.setter
    def webhook_secret(self, value: str) -> None:
        self.webhook_secret_encrypted = encrypt(value) if value else ""


class TeamMember(BaseDomainModel):
    """Membership of a ``User`` in a ``Merchant`` with a role."""

    class Status(models.TextChoices):
        INVITED = "invited", _("Invited")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="team_members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    role = models.CharField(max_length=32, choices=Role.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_teammember"
        constraints = [
            models.UniqueConstraint(fields=["merchant", "user"], name="uniq_merchant_user"),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.user.email}@{self.merchant.slug}:{self.role}"


class ApiKey(BaseDomainModel):
    """Hashed API key, scoped to one merchant + environment."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        REVOKED = "revoked", _("Revoked")

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="api_keys")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=128)
    key_prefix = models.CharField(max_length=24, db_index=True)  # e.g. "nse_test_a1b2"
    key_hash = models.CharField(max_length=128, unique=True)
    scopes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "accounts_apikey"
        indexes = [
            models.Index(fields=["merchant", "environment", "status"], name="apikey_scope_status_idx"),
        ]

    @staticmethod
    def hash_secret(secret: str) -> str:
        """Public hashing helper so ``authentication.py`` and services share one impl."""
        return hash_secret(secret)


class EmailVerificationToken(BaseDomainModel):
    """One-shot token consumed by ``POST /api/v1/auth/verify-email``.

    ``user`` is null while signup is pending verification (the User row is
    created only once the token is consumed). ``pending_payload`` carries the
    ``fullName``, ``orgName``, hashed password, etc., until then.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name="verification_tokens"
    )
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=128, unique=True, db_index=True)
    pending_payload = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_emailverificationtoken"
        indexes = [models.Index(fields=["email", "-created_at"], name="email_verif_email_time_idx")]


class PasswordResetToken(BaseDomainModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_passwordresettoken"


class MfaChallenge(BaseDomainModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_challenges")
    challenge_id = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounts_mfachallenge"
