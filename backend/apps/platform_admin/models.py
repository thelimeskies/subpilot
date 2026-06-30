"""Platform admin domain models.

This module defines the auth identity (``PlatformAdmin``) and ancillary
models used by the operator console. The model is **not** a Django
``AbstractUser`` and **not** registered as ``AUTH_USER_MODEL`` — keeping
it cleanly outside the merchant auth surface.
"""
from __future__ import annotations

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.crypto import decrypt, encrypt
from apps.common.models import BaseDomainModel


class PlatformAdminRole(models.TextChoices):
    OWNER = "owner", _("Owner")
    OPERATOR = "operator", _("Operator")
    SUPPORT = "support", _("Support")
    READ_ONLY = "read_only", _("Read-only")


class PlatformAdminStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    INVITED = "invited", _("Invited")
    SUSPENDED = "suspended", _("Suspended")


class PlatformAdmin(BaseDomainModel):
    """SubPilot internal staff identity.

    Authenticates against ``password_hash`` (Argon2 via Django hashers).
    Acts as a DRF ``request.user`` substitute for ``/api/v1/platform/*``;
    must satisfy the duck-typed interface (``is_authenticated`` etc.)
    expected by ``IsAuthenticated``.
    """

    email = models.EmailField(unique=True, db_index=True)
    display_name = models.CharField(max_length=128, blank=True, default="")
    password_hash = models.CharField(max_length=256, blank=True, default="")
    role = models.CharField(
        max_length=16,
        choices=PlatformAdminRole.choices,
        default=PlatformAdminRole.OPERATOR,
    )
    status = models.CharField(
        max_length=16,
        choices=PlatformAdminStatus.choices,
        default=PlatformAdminStatus.ACTIVE,
    )
    last_login_at = models.DateTimeField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        db_table = "platform_admin_platformadmin"
        verbose_name = "Platform admin"
        verbose_name_plural = "Platform admins"

    # --- Duck-typed user interface for DRF ----------------------------------
    @property
    def is_authenticated(self) -> bool:  # noqa: D401
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def is_active(self) -> bool:
        return self.status == PlatformAdminStatus.ACTIVE

    @property
    def is_staff(self) -> bool:
        # Intentionally False — never collide with TenantContextMiddleware
        # at apps/accounts/middleware.py:49.
        return False

    @property
    def is_superuser(self) -> bool:
        return False

    @property
    def pk_str(self) -> str:
        return str(self.pk)

    @property
    def initials(self) -> str:
        source = self.display_name or self.email
        parts = [p for p in source.replace("@", " ").split() if p]
        if not parts:
            return "P"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    # --- Password helpers ---------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    # --- MFA convenience ----------------------------------------------------
    @property
    def mfa_secret(self) -> str:
        return decrypt(self.mfa_secret_encrypted)

    @mfa_secret.setter
    def mfa_secret(self, value: str) -> None:
        self.mfa_secret_encrypted = encrypt(value) if value else ""

    def touch_login(self) -> None:
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at", "updated_at"])

    def __str__(self) -> str:  # pragma: no cover
        return f"<PlatformAdmin {self.email} role={self.role}>"


class PlatformMerchantNote(BaseDomainModel):
    """Free-form note attached to a merchant by a platform admin (S4)."""

    merchant = models.ForeignKey(
        "accounts.Merchant",
        on_delete=models.CASCADE,
        related_name="platform_notes",
    )
    author = models.ForeignKey(
        PlatformAdmin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = models.TextField()

    class Meta:
        db_table = "platform_admin_merchantnote"
        ordering = ["-created_at"]


class SupportTicketStatus(models.TextChoices):
    OPEN = "open", _("Open")
    IN_PROGRESS = "in_progress", _("In progress")
    RESOLVED = "resolved", _("Resolved")
    CLOSED = "closed", _("Closed")


class SupportTicketPriority(models.TextChoices):
    LOW = "low", _("Low")
    NORMAL = "normal", _("Normal")
    HIGH = "high", _("High")
    URGENT = "urgent", _("Urgent")


class SupportTicket(BaseDomainModel):
    """Cross-tenant support ticket the platform team works on (S8)."""

    merchant = models.ForeignKey(
        "accounts.Merchant",
        on_delete=models.CASCADE,
        related_name="+",
    )
    subject = models.CharField(max_length=256)
    body = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=16,
        choices=SupportTicketPriority.choices,
        default=SupportTicketPriority.NORMAL,
    )
    status = models.CharField(
        max_length=16,
        choices=SupportTicketStatus.choices,
        default=SupportTicketStatus.OPEN,
    )
    assignee = models.ForeignKey(
        PlatformAdmin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    requester_email = models.EmailField(blank=True, default="")

    class Meta:
        db_table = "platform_admin_supportticket"
        ordering = ["-created_at"]


class SupportTicketReply(BaseDomainModel):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        PlatformAdmin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    body = models.TextField()

    class Meta:
        db_table = "platform_admin_supportticketreply"
        ordering = ["created_at"]


class KycStatus(models.TextChoices):
    VERIFIED = "verified", _("Verified")
    IN_REVIEW = "in_review", _("In review")
    REJECTED = "rejected", _("Rejected")
    ACTION_NEEDED = "action_needed", _("Action needed")


class KycLevel(models.TextChoices):
    TIER_1 = "tier_1", _("Tier 1")
    TIER_2 = "tier_2", _("Tier 2")
    TIER_3 = "tier_3", _("Tier 3")


class KycReview(BaseDomainModel):
    merchant = models.OneToOneField(
        "accounts.Merchant",
        on_delete=models.CASCADE,
        related_name="kyc_review",
    )
    status = models.CharField(
        max_length=16,
        choices=KycStatus.choices,
        default=KycStatus.IN_REVIEW,
    )
    level = models.CharField(
        max_length=16,
        choices=KycLevel.choices,
        default=KycLevel.TIER_1,
    )
    documents = models.JSONField(default=list, blank=True)
    flags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True, default="")
    reviewer = models.ForeignKey(
        PlatformAdmin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_admin_kycreview"


class PlatformInviteToken(BaseDomainModel):
    """Single-use invite token for new platform admins (S9)."""

    admin = models.ForeignKey(
        PlatformAdmin,
        on_delete=models.CASCADE,
        related_name="invite_tokens",
    )
    token = models.CharField(max_length=128, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_admin_invitetoken"


class PlatformSetting(BaseDomainModel):
    """Singleton row holding platform-wide policy + adapter status (S10)."""

    key = models.CharField(max_length=64, unique=True, default="default")
    policy = models.JSONField(default=dict, blank=True)
    adapter_status = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_admin_setting"


class MerchantConfig(BaseDomainModel):
    """Per-merchant operational overrides + feature flag map (S13).

    Sits 1:1 with [Merchant](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/accounts/models.py#L148-L168).
    All three JSON columns are sparse overrides on top of the canonical
    defaults defined in
    [feature_flags.py](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/platform_admin/feature_flags.py)
    and [PlatformSetting](file:///Users/mac/Desktop/Projects/HackathonxNomba/backend/apps/platform_admin/models.py#L278-L286).
    """

    merchant = models.OneToOneField(
        "accounts.Merchant",
        on_delete=models.CASCADE,
        related_name="config",
    )
    # Sparse override map: ``{flag_key: bool}``. Missing keys fall back to
    # the catalog default. Unknown keys are rejected at the service layer.
    feature_flags = models.JSONField(default=dict, blank=True)
    # ``{monthly_volume_cap_minor:int, max_ticket_minor:int, high_risk_mcc:bool,
    #    payout_cadence:str, notification_channels:list[str], currency:str}``
    limits = models.JSONField(default=dict, blank=True)
    # ``{attempts:int, backoff:'linear'|'exponential', cooldown_hours:int}``
    retry_policy = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        PlatformAdmin,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "platform_admin_merchantconfig"

    def __str__(self) -> str:  # pragma: no cover
        return f"<MerchantConfig merchant={self.merchant_id}>"
