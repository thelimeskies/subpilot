import { useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  SegmentedControl,
  SelectInput,
  Sheet,
  Tabs,
  TextInput
} from "@subpilot/ui";
import {
  Activity,
  AlertTriangle,
  Cable,
  Copy,
  KeyRound,
  LogOut,
  Pause,
  PauseCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sliders
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth, usePlatformPermissions } from "../auth/AuthContext";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { api } from "../api/client";
import { useSettings, type AdapterRow, type PlatformPolicy } from "../api/settings";
import { useAuditLog, type AuditCategory } from "../api/audit";

type TabKey = "platform" | "adapters" | "webhooks" | "security" | "data" | "branding" | "audit" | "profile";

// Mirrors backend selectors.settings.DEFAULT_POLICY so the page renders
// without a flash of empty fields while the hook is still loading.
const FALLBACK_POLICY: PlatformPolicy = {
  defaultRetryAttempts: 4,
  defaultBackoff: "Exponential",
  defaultCooldownHours: 6,
  webhookSignatureHeader: "X-SubPilot-Signature",
  webhookSignatureKeyAge: "Rolled 12 days ago",
  passwordMinLength: 12,
  sessionLifetimeHours: 12,
  ipAllowlistEnabled: false,
  enforcedMfa: true,
  dataRetentionDays: 540,
  readOnlyMode: false,
  blockNewSignups: false,
  webhookDeliveriesEnabled: true,
  cardTokenizationEnabled: true,
  bankTransferRecoveryEnabled: true,
  ssoGoogleEnabled: true,
  sessionTimeoutEnabled: true,
  blockNewCountriesEnabled: false,
  passwordRotationDays: 90,
  passwordHistoryCount: 5,
  passwordLockoutThreshold: 6,
  verifyHmacOnReceipts: true,
  enforceTls13: true,
  requireIdempotencyKey: true,
  allowSelfSignedDevEndpoints: false,
  webhookDeliveryRetentionDays: 30,
  tokenizedCardRetentionDays: 730,
  customerProfileRetention: "forever",
  brandDisplayName: "SubPilot",
  brandSupportEmail: "support@subpilot.dev",
  brandPrimaryColor: "#0BBF85",
  brandAccentColor: "#0F2A2E",
  routingStrategy: "smart",
  autoFailoverOn5xx: true,
  retryOnDifferentAdapter: true,
  forceFailoverOverride: false,
  webhookSignatureAlgorithm: "hmac-sha256",
  webhookTimestampToleranceSeconds: 300,
  webhookReplayWindowMinutes: 10,
  webhookTimeoutSeconds: 20,
  webhookConcurrencyPerMerchant: 16,
  subscribedEventTypes: [
    "subscription.created",
    "subscription.updated",
    "subscription.canceled",
    "invoice.paid",
    "invoice.failed",
    "invoice.recovered",
    "payment.captured",
    "payment.refunded",
    "customer.card_updated",
  ],
  dunningEmailD1: true,
  dunningEmailSmsD3: true,
  dunningFinalNoticeD7: true,
  dunningAutoPauseD10: true,
};

export function SettingsPage() {
  const { user, signOut, updateProfile } = useAuth();
  const { canEditSettings } = usePlatformPermissions();
  const navigate = useNavigate();
  const { notify, confirm } = useFeedback();
  const [tab, setTab] = useState<TabKey>("platform");

  const { settings, loading, error, update } = useSettings();
  const policy: PlatformPolicy = useMemo(
    () => ({ ...FALLBACK_POLICY, ...(settings?.policy ?? {}) }),
    [settings],
  );
  const adapters: AdapterRow[] = settings?.adapterStatus ?? [];

  const [auditCategory, setAuditCategory] = useState<AuditCategory | "">("");
  const {
    rows: auditEntries,
    total: auditTotal,
    loading: auditLoading,
    error: auditError,
    reload: reloadAudit,
  } = useAuditLog({ pageSize: 50, category: auditCategory });

  const [retryOpen, setRetryOpen] = useState(false);
  const [signingOpen, setSigningOpen] = useState(false);
  const [adapterFor, setAdapterFor] = useState<AdapterRow | null>(null);
  const [pauseAllOpen, setPauseAllOpen] = useState(false);
  const [rotateOpen, setRotateOpen] = useState(false);

  // Form state — segmented controls need real handlers to feel responsive
  const [routingStrategy, setRoutingStrategy] = useState<string>(policy.routingStrategy);
  const [rotateChannel, setRotateChannel] = useState<string>("email-webhook");
  const [retryBackoff, setRetryBackoff] = useState<string>(policy.defaultBackoff);
  const [retryAttempts, setRetryAttempts] = useState<string>(String(policy.defaultRetryAttempts));
  const [retryCooldown, setRetryCooldown] = useState<string>(String(policy.defaultCooldownHours));
  const [retryTimeout, setRetryTimeout] = useState<string>(String(policy.webhookTimeoutSeconds));
  const [retryConcurrency, setRetryConcurrency] = useState<string>(String(policy.webhookConcurrencyPerMerchant));
  const [savingPolicy, setSavingPolicy] = useState(false);

  // --- Webhook signing config sheet state -------------------------------
  const [signingHeader, setSigningHeader] = useState<string>(policy.webhookSignatureHeader);
  const [signingAlgorithm, setSigningAlgorithm] = useState<string>(policy.webhookSignatureAlgorithm);
  const [signingTolerance, setSigningTolerance] = useState<string>(String(policy.webhookTimestampToleranceSeconds));
  const [signingReplayWindow, setSigningReplayWindow] = useState<string>(String(policy.webhookReplayWindowMinutes));
  const [savingSigning, setSavingSigning] = useState(false);

  // --- Profile tab editable state -----------------------------------------
  const [profileName, setProfileName] = useState(user?.name ?? "");
  const [profileEmail, setProfileEmail] = useState(user?.email ?? "");
  const [savingProfile, setSavingProfile] = useState(false);
  useEffect(() => {
    setProfileName(user?.name ?? "");
    setProfileEmail(user?.email ?? "");
  }, [user?.name, user?.email]);

  // --- Security tab editable form state ----------------------------------
  const [pwMinLength, setPwMinLength] = useState(String(policy.passwordMinLength));
  const [pwRotationDays, setPwRotationDays] = useState(String(policy.passwordRotationDays));
  const [pwHistoryCount, setPwHistoryCount] = useState(String(policy.passwordHistoryCount));
  const [pwLockoutThreshold, setPwLockoutThreshold] = useState(String(policy.passwordLockoutThreshold));
  const [savingSecurity, setSavingSecurity] = useState(false);

  // --- Data tab editable form state --------------------------------------
  const [auditRetentionDays, setAuditRetentionDays] = useState(String(policy.dataRetentionDays));
  const [webhookRetentionDays, setWebhookRetentionDays] = useState(String(policy.webhookDeliveryRetentionDays));
  const [cardRetentionDays, setCardRetentionDays] = useState(String(policy.tokenizedCardRetentionDays));
  const [customerRetention, setCustomerRetention] = useState(policy.customerProfileRetention);
  const [savingData, setSavingData] = useState(false);

  // --- Branding tab editable form state ----------------------------------
  const [brandName, setBrandName] = useState(policy.brandDisplayName);
  const [brandEmail, setBrandEmail] = useState(policy.brandSupportEmail);
  const [brandPrimary, setBrandPrimary] = useState(policy.brandPrimaryColor);
  const [brandAccent, setBrandAccent] = useState(policy.brandAccentColor);
  const [savingBranding, setSavingBranding] = useState(false);

  // When settings load, sync the editable form state to the latest server values.
  useEffect(() => {
    setRetryBackoff(policy.defaultBackoff);
    setRetryAttempts(String(policy.defaultRetryAttempts));
    setRetryCooldown(String(policy.defaultCooldownHours));
    setRetryTimeout(String(policy.webhookTimeoutSeconds));
    setRetryConcurrency(String(policy.webhookConcurrencyPerMerchant));
    setRoutingStrategy(policy.routingStrategy);
    setSigningHeader(policy.webhookSignatureHeader);
    setSigningAlgorithm(policy.webhookSignatureAlgorithm);
    setSigningTolerance(String(policy.webhookTimestampToleranceSeconds));
    setSigningReplayWindow(String(policy.webhookReplayWindowMinutes));
  }, [
    policy.defaultBackoff,
    policy.defaultRetryAttempts,
    policy.defaultCooldownHours,
    policy.webhookTimeoutSeconds,
    policy.webhookConcurrencyPerMerchant,
    policy.routingStrategy,
    policy.webhookSignatureHeader,
    policy.webhookSignatureAlgorithm,
    policy.webhookTimestampToleranceSeconds,
    policy.webhookReplayWindowMinutes,
  ]);

  useEffect(() => {
    setPwMinLength(String(policy.passwordMinLength));
    setPwRotationDays(String(policy.passwordRotationDays));
    setPwHistoryCount(String(policy.passwordHistoryCount));
    setPwLockoutThreshold(String(policy.passwordLockoutThreshold));
  }, [
    policy.passwordMinLength,
    policy.passwordRotationDays,
    policy.passwordHistoryCount,
    policy.passwordLockoutThreshold,
  ]);

  useEffect(() => {
    setAuditRetentionDays(String(policy.dataRetentionDays));
    setWebhookRetentionDays(String(policy.webhookDeliveryRetentionDays));
    setCardRetentionDays(String(policy.tokenizedCardRetentionDays));
    setCustomerRetention(policy.customerProfileRetention);
  }, [
    policy.dataRetentionDays,
    policy.webhookDeliveryRetentionDays,
    policy.tokenizedCardRetentionDays,
    policy.customerProfileRetention,
  ]);

  useEffect(() => {
    setBrandName(policy.brandDisplayName);
    setBrandEmail(policy.brandSupportEmail);
    setBrandPrimary(policy.brandPrimaryColor);
    setBrandAccent(policy.brandAccentColor);
  }, [
    policy.brandDisplayName,
    policy.brandSupportEmail,
    policy.brandPrimaryColor,
    policy.brandAccentColor,
  ]);

  // Surface a one-time toast when the API errors. We don't block the UI —
  // FALLBACK_POLICY keeps the page usable.
  useEffect(() => {
    if (error) {
      notify({ tone: "warning", title: "Settings unavailable", description: error });
    }
  }, [error, notify]);

  function handleSignOut() {
    void signOut();
    navigate("/sign-in", { replace: true });
  }

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard?.writeText(value);
      notify({ tone: "success", title: "Copied", description: `${label} copied to clipboard.` });
    } catch {
      notify({ tone: "warning", title: "Copy unavailable", description: "Clipboard access was blocked." });
    }
  }

  function handleSave(label: string) {
    notify({ tone: "success", title: "Changes saved", description: `${label} updated platform-wide.` });
  }

  function handleDiscard() {
    notify({ tone: "info", title: "Changes discarded", description: "No edits were applied." });
  }

  function handleEdit(field: string) {
    notify({ tone: "info", title: `Editing ${field}`, description: "Opens the inline editor for this profile field." });
  }

  function handleExport(label: string) {
    notify({ tone: "info", title: "Export queued", description: `${label} is being prepared. We'll email the file when ready.` });
  }

  // ----- Profile tab ------------------------------------------------------
  async function handleSaveProfile() {
    const trimmedName = profileName.trim();
    const trimmedEmail = profileEmail.trim();
    if (!trimmedName) {
      notify({ tone: "warning", title: "Display name required", description: "Enter your full name." });
      return;
    }
    if (!trimmedEmail) {
      notify({ tone: "warning", title: "Email required", description: "Enter your work email." });
      return;
    }
    setSavingProfile(true);
    try {
      const result = await updateProfile({ name: trimmedName, email: trimmedEmail });
      if (!result.ok) {
        notify({ tone: "danger", title: "Could not update profile", description: result.reason });
        return;
      }
      notify({ tone: "success", title: "Profile updated", description: "Your changes are visible across the audit log." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not update profile", description: err instanceof Error ? err.message : "Try again." });
    } finally {
      setSavingProfile(false);
    }
  }

  function handleDiscardProfile() {
    setProfileName(user?.name ?? "");
    setProfileEmail(user?.email ?? "");
    notify({ tone: "info", title: "Changes discarded", description: "Reverted to your saved profile." });
  }

  // ----- Security tab -----------------------------------------------------
  async function handleSaveSecurity() {
    const minLen = Number.parseInt(pwMinLength, 10);
    const rotation = Number.parseInt(pwRotationDays, 10);
    const history = Number.parseInt(pwHistoryCount, 10);
    const lockout = Number.parseInt(pwLockoutThreshold, 10);
    if ([minLen, rotation, history, lockout].some((n) => !Number.isFinite(n) || n < 0)) {
      notify({ tone: "warning", title: "Invalid password policy", description: "All values must be non-negative integers." });
      return;
    }
    setSavingSecurity(true);
    try {
      await update({
        policy: {
          passwordMinLength: minLen,
          passwordRotationDays: rotation,
          passwordHistoryCount: history,
          passwordLockoutThreshold: lockout,
        },
      });
      notify({ tone: "success", title: "Password policy saved", description: "New policy applies to future sign-ins." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not save password policy", description: err instanceof Error ? err.message : "Try again." });
    } finally {
      setSavingSecurity(false);
    }
  }

  // ----- Data tab ---------------------------------------------------------
  async function handleSaveDataRetention() {
    const audit = Number.parseInt(auditRetentionDays, 10);
    const webhook = Number.parseInt(webhookRetentionDays, 10);
    const card = Number.parseInt(cardRetentionDays, 10);
    if ([audit, webhook, card].some((n) => !Number.isFinite(n) || n < 0)) {
      notify({ tone: "warning", title: "Invalid retention value", description: "Days must be non-negative integers." });
      return;
    }
    setSavingData(true);
    try {
      await update({
        policy: {
          dataRetentionDays: audit,
          webhookDeliveryRetentionDays: webhook,
          tokenizedCardRetentionDays: card,
          customerProfileRetention: customerRetention,
        },
      });
      notify({ tone: "success", title: "Retention saved", description: "New retention policy will apply to nightly purges." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not save retention", description: err instanceof Error ? err.message : "Try again." });
    } finally {
      setSavingData(false);
    }
  }

  // ----- Branding tab -----------------------------------------------------
  async function handleSaveBranding() {
    const name = brandName.trim();
    const email = brandEmail.trim();
    if (!name) {
      notify({ tone: "warning", title: "Display name required", description: "Brand name cannot be empty." });
      return;
    }
    if (!email) {
      notify({ tone: "warning", title: "Support email required", description: "Customers see this on every receipt." });
      return;
    }
    setSavingBranding(true);
    try {
      await update({
        policy: {
          brandDisplayName: name,
          brandSupportEmail: email,
          brandPrimaryColor: brandPrimary,
          brandAccentColor: brandAccent,
        },
      });
      notify({ tone: "success", title: "Branding saved", description: "Updated portal and email templates." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not save branding", description: err instanceof Error ? err.message : "Try again." });
    } finally {
      setSavingBranding(false);
    }
  }

  async function handleReadOnlyMode() {
    const ok = await confirm({
      title: "Enable platform read-only mode?",
      description: "All merchants will lose write access to billing primitives until you disable read-only mode.",
      confirmLabel: "Enable read-only",
      destructive: true
    });
    if (!ok) return;
    try {
      await update({ policy: { readOnlyMode: true } });
      notify({
        tone: "warning",
        title: "Read-only mode enabled",
        description: "Writes are blocked platform-wide. Disable from this page when the incident is resolved."
      });
    } catch (err) {
      const reason = err instanceof Error ? err.message : "Could not enable read-only mode.";
      notify({ tone: "danger", title: "Could not enable read-only mode", description: reason });
    }
  }

  async function handleSaveRetryPolicy() {
    const attempts = Number.parseInt(retryAttempts, 10);
    const cooldown = Number.parseInt(retryCooldown, 10);
    const timeout = Number.parseInt(retryTimeout, 10);
    const concurrency = Number.parseInt(retryConcurrency, 10);
    if (!Number.isFinite(attempts) || attempts < 0) {
      notify({ tone: "warning", title: "Invalid retry attempts", description: "Enter a non-negative integer." });
      return;
    }
    if (!Number.isFinite(cooldown) || cooldown < 0) {
      notify({ tone: "warning", title: "Invalid cooldown", description: "Enter a non-negative integer." });
      return;
    }
    if (!Number.isFinite(timeout) || timeout <= 0) {
      notify({ tone: "warning", title: "Invalid timeout", description: "Timeout must be a positive integer." });
      return;
    }
    if (!Number.isFinite(concurrency) || concurrency <= 0) {
      notify({ tone: "warning", title: "Invalid concurrency", description: "Concurrency must be a positive integer." });
      return;
    }
    setSavingPolicy(true);
    try {
      await update({
        policy: {
          defaultRetryAttempts: attempts,
          defaultCooldownHours: cooldown,
          defaultBackoff: retryBackoff,
          webhookTimeoutSeconds: timeout,
          webhookConcurrencyPerMerchant: concurrency,
        },
      });
      setRetryOpen(false);
      notify({
        tone: "success",
        title: "Retry policy saved",
        description: "New defaults apply to merchants without custom retry settings."
      });
    } catch (err) {
      const reason = err instanceof Error ? err.message : "Could not save retry policy.";
      notify({ tone: "danger", title: "Could not save retry policy", description: reason });
    } finally {
      setSavingPolicy(false);
    }
  }

  // ----- Adapters tab routing strategy -----------------------------------
  async function handleChangeRoutingStrategy(next: string) {
    setRoutingStrategy(next);
    if (next === policy.routingStrategy) return;
    try {
      await update({ policy: { routingStrategy: next } });
      notify({ tone: "success", title: "Routing strategy saved", description: `Now using ${next} routing.` });
    } catch (err) {
      setRoutingStrategy(policy.routingStrategy);
      notify({ tone: "danger", title: "Could not save routing strategy", description: err instanceof Error ? err.message : "Try again." });
    }
  }

  // ----- Webhooks tab subscribed events ----------------------------------
  async function handleToggleEventType(evt: string) {
    const current = policy.subscribedEventTypes ?? [];
    const next = current.includes(evt) ? current.filter((e) => e !== evt) : [...current, evt];
    try {
      await update({ policy: { subscribedEventTypes: next } });
      notify({ tone: "info", title: `${evt} ${next.includes(evt) ? "enabled" : "disabled"}`, description: "Subscription list updated." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not toggle event", description: err instanceof Error ? err.message : "Try again." });
    }
  }

  // ----- Webhooks signing config sheet -----------------------------------
  async function handleSaveSigningConfig() {
    const header = signingHeader.trim();
    if (!header) {
      notify({ tone: "warning", title: "Header required", description: "Signature header cannot be empty." });
      return;
    }
    const tolerance = Number.parseInt(signingTolerance, 10);
    const replay = Number.parseInt(signingReplayWindow, 10);
    if (!Number.isFinite(tolerance) || tolerance < 0) {
      notify({ tone: "warning", title: "Invalid tolerance", description: "Tolerance must be a non-negative integer." });
      return;
    }
    if (!Number.isFinite(replay) || replay < 0) {
      notify({ tone: "warning", title: "Invalid replay window", description: "Replay window must be a non-negative integer." });
      return;
    }
    setSavingSigning(true);
    try {
      await update({
        policy: {
          webhookSignatureHeader: header,
          webhookSignatureAlgorithm: signingAlgorithm,
          webhookTimestampToleranceSeconds: tolerance,
          webhookReplayWindowMinutes: replay,
        },
      });
      setSigningOpen(false);
      notify({ tone: "success", title: "Signing config saved", description: "Header naming and verification settings updated." });
    } catch (err) {
      notify({ tone: "danger", title: "Could not save signing config", description: err instanceof Error ? err.message : "Try again." });
    } finally {
      setSavingSigning(false);
    }
  }

  async function handlePauseAllWebhooks() {
    setPauseAllOpen(false);
    try {
      await update({ policy: { webhookDeliveriesEnabled: false } });
      notify({
        tone: "danger",
        title: "All webhooks paused",
        description: "Outbound deliveries are queued. Resume from the danger zone when the incident is resolved."
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not pause webhooks",
        description: err instanceof Error ? err.message : "Try again.",
      });
    }
  }

  async function handleRotateSigningKey() {
    setRotateOpen(false);
    try {
      const body = await api.post<{
        ok: boolean;
        fingerprint: string;
        rotatedAt: string;
        gracePeriod: string;
        reason?: string;
      }>("/platform/webhooks/rotate-key", {
        grace_period: "48h",
        notify_channel: rotateChannel,
      });
      if (!body.ok) throw new Error(body.reason || "Could not rotate key.");
      notify({
        tone: "warning",
        title: "Signing key rotated",
        description: `New fingerprint ${body.fingerprint}. Previous key honored for ${body.gracePeriod}.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not rotate key",
        description: err instanceof Error ? err.message : "Try again.",
      });
    }
  }

  async function handleSaveAdapter() {
    if (!adapterFor) return;
    const next = adapters.map((a) => (a.name === adapterFor.name ? adapterFor : a));
    const exists = adapters.some((a) => a.name === adapterFor.name);
    const payload = exists ? next : [...adapters, adapterFor];
    setAdapterFor(null);
    try {
      await update({ adapterStatus: payload });
      notify({
        tone: "success",
        title: "Adapter saved",
        description: `${adapterFor.name} routing and failover settings updated.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save adapter",
        description: err instanceof Error ? err.message : "Try again.",
      });
    }
  }

  function handleAddAdapter() {
    setAdapterFor({
      name: "New adapter",
      role: "Backup processor",
      uptime: "—",
      latencyP95: "—",
      failoverTrigger: "5xx > 5% over 5 minutes",
      region: "Lagos",
      status: "Monitoring",
    });
  }

  async function handleTogglePolicy(key: keyof PlatformPolicy, label: string) {
    const current = Boolean(policy[key]);
    try {
      await update({ policy: { [key]: !current } as Partial<PlatformPolicy> });
      notify({
        tone: "info",
        title: `${label} ${!current ? "enabled" : "disabled"}`,
        description: `Updated platform-wide.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: `Could not toggle ${label}`,
        description: err instanceof Error ? err.message : "Try again.",
      });
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={<span className="adm-kicker">Platform configuration</span>}
        title="Settings"
        description="Adapter routing, retry policy, signing keys, security posture, branding, and the platform-wide audit trail."
        actions={
          <>
            <Button
              variant="ghost"
              icon={<Activity size={16} />}
              onClick={() => window.open("https://status.subpilot.dev", "_blank", "noopener")}
            >
              Status page
            </Button>
            <Button variant="ghost" icon={<LogOut size={16} />} onClick={handleSignOut}>Sign out</Button>
          </>
        }
      />

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Platform", value: "platform" },
          { label: "Adapters", value: "adapters", count: adapters.length },
          { label: "Webhooks", value: "webhooks" },
          { label: "Security", value: "security" },
          { label: "Data", value: "data" },
          { label: "Branding", value: "branding" },
          { label: "Audit", value: "audit", count: auditTotal },
          { label: "Profile", value: "profile" }
        ]}
      />

      {tab === "platform" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader
              title="Default retry policy"
              description="Applied to every merchant unless they override it on their detail page."
              action={canEditSettings ? <Button icon={<Sliders size={14} />} onClick={() => setRetryOpen(true)}>Edit policy</Button> : undefined}
            />
            <dl className="adm-defs">
              <div><dt>Retry attempts</dt><dd>{policy.defaultRetryAttempts}</dd></div>
              <div><dt>Backoff strategy</dt><dd>{policy.defaultBackoff}</dd></div>
              <div><dt>Cooldown</dt><dd>{policy.defaultCooldownHours} hours</dd></div>
              <div><dt>Dunning emails</dt><dd>D+1, D+3, D+7</dd></div>
              <div><dt>Smart routing</dt><dd>Enabled platform-wide</dd></div>
              <div><dt>Auto-suspend on chargebacks &gt; 1.5%</dt><dd>Enabled</dd></div>
            </dl>
          </Card>

          <Card tone="mint">
            <CardHeader title="Operational toggles" description="Killswitches that affect every merchant." />
            <ul className="adm-toggle-list">
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.webhookDeliveriesEnabled}
                  onChange={() => handleTogglePolicy("webhookDeliveriesEnabled", "Webhook deliveries")}
                />
                <strong>Webhook deliveries enabled</strong>
                <Badge tone={policy.webhookDeliveriesEnabled ? "success" : "neutral"}>{policy.webhookDeliveriesEnabled ? "On" : "Off"}</Badge>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.cardTokenizationEnabled}
                  onChange={() => handleTogglePolicy("cardTokenizationEnabled", "Card tokenization")}
                />
                <strong>Card tokenization</strong>
                <Badge tone={policy.cardTokenizationEnabled ? "success" : "neutral"}>{policy.cardTokenizationEnabled ? "On" : "Off"}</Badge>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.bankTransferRecoveryEnabled}
                  onChange={() => handleTogglePolicy("bankTransferRecoveryEnabled", "Bank transfer recovery")}
                />
                <strong>Bank transfer recovery</strong>
                <Badge tone={policy.bankTransferRecoveryEnabled ? "success" : "neutral"}>{policy.bankTransferRecoveryEnabled ? "On" : "Off"}</Badge>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.readOnlyMode}
                  onChange={() => handleTogglePolicy("readOnlyMode", "Read-only mode")}
                />
                <strong>Read-only mode (incident)</strong>
                <Badge tone={policy.readOnlyMode ? "warning" : "neutral"}>{policy.readOnlyMode ? "On" : "Off"}</Badge>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.blockNewSignups}
                  onChange={() => handleTogglePolicy("blockNewSignups", "Block new signups")}
                />
                <strong>Block new merchant signups</strong>
                <Badge tone={policy.blockNewSignups ? "warning" : "neutral"}>{policy.blockNewSignups ? "On" : "Off"}</Badge>
              </li>
            </ul>
          </Card>

          <Card>
            <CardHeader title="Dunning & recovery" description="Default cadence applied to every merchant." />
            <table className="sp-table">
              <thead><tr><th>Step</th><th>When</th><th>Channel</th><th>Action</th></tr></thead>
              <tbody>
                <tr><td>1</td><td>D+0 fail</td><td>Email + Webhook</td><td>Notify customer + retry</td></tr>
                <tr><td>2</td><td>D+1</td><td>Email</td><td>Reminder with portal link</td></tr>
                <tr><td>3</td><td>D+3</td><td>Email + SMS</td><td>Update card prompt</td></tr>
                <tr><td>4</td><td>D+7</td><td>Email</td><td>Final notice + grace period</td></tr>
                <tr><td>5</td><td>D+10</td><td>System</td><td>Subscription paused</td></tr>
              </tbody>
            </table>
          </Card>
        </section>
      ) : null}

      {tab === "adapters" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader
              title="Payment adapters"
              description="Active processors and routing rules. SubPilot can fail over automatically."
              action={
                canEditSettings ? (
                  <Button
                    variant="ghost"
                    icon={<Cable size={14} />}
                    onClick={handleAddAdapter}
                  >
                    Add adapter
                  </Button>
                ) : undefined
              }
            />
            <table className="sp-table">
              <thead><tr><th>Adapter</th><th>Role</th><th>Region</th><th>Uptime</th><th>p95 latency</th><th>Failover trigger</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {adapters.map((a) => (
                  <tr key={a.name}>
                    <td><strong>{a.name}</strong></td>
                    <td>{a.role}</td>
                    <td><span className="adm-muted">{a.region}</span></td>
                    <td>{a.uptime}</td>
                    <td>{a.latencyP95}</td>
                    <td><span className="adm-muted">{a.failoverTrigger}</span></td>
                    <td><Badge tone={a.status === "Operational" ? "success" : "warning"}>{a.status}</Badge></td>
                    <td className="sp-align-right">{canEditSettings ? <Button variant="ghost" onClick={() => setAdapterFor(a)}>Configure</Button> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card tone="mint">
            <CardHeader title="Routing strategy" description="How SubPilot picks an adapter for each charge." />
            <SegmentedControl
              label="Strategy"
              value={routingStrategy}
              onChange={(v) => void handleChangeRoutingStrategy(v)}
              items={[
                { label: "Smart routing", value: "smart" },
                { label: "Primary only", value: "primary" },
                { label: "Round-robin", value: "round" }
              ]}
            />
            <ul className="adm-toggle-list">
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.autoFailoverOn5xx}
                  onChange={() => handleTogglePolicy("autoFailoverOn5xx", "Auto-failover on 5xx burst")}
                />
                <strong>Auto-failover on 5xx burst</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.retryOnDifferentAdapter}
                  onChange={() => handleTogglePolicy("retryOnDifferentAdapter", "Retry on different adapter")}
                />
                <strong>Retry on different adapter</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.forceFailoverOverride}
                  onChange={() => handleTogglePolicy("forceFailoverOverride", "Force failover override")}
                />
                <strong>Force failover (manual override)</strong>
              </li>
            </ul>
          </Card>
        </section>
      ) : null}

      {tab === "webhooks" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader
              title="Signing key"
              description={`Header: ${policy.webhookSignatureHeader} · ${policy.webhookSignatureKeyAge}`}
              action={canEditSettings ? <Button icon={<KeyRound size={14} />} onClick={() => setRotateOpen(true)}>Rotate platform key</Button> : undefined}
            />
            <div className="adm-key-row">
              <code className="adm-code adm-code--block">whsec_••••••••••••••••••••••••••••••••a8f3</code>
              <Button
                variant="ghost"
                icon={<Copy size={14} />}
                onClick={() => copyText("whsec_••••••••••••••••••••••••••••••••a8f3", "Signing key")}
              >
                Copy
              </Button>
            </div>
            <p className="adm-muted">All outbound webhooks are signed with HMAC-SHA256. Previous keys remain valid during the rotation grace window.</p>
          </Card>

          <Card>
            <CardHeader title="Delivery defaults" description="Used when a merchant has not set their own retry policy." />
            <dl className="adm-defs">
              <div><dt>Retry attempts</dt><dd>{policy.defaultRetryAttempts}</dd></div>
              <div><dt>Backoff</dt><dd>{policy.defaultBackoff}</dd></div>
              <div><dt>Cooldown</dt><dd>{policy.defaultCooldownHours}h</dd></div>
              <div><dt>Timeout</dt><dd>{policy.webhookTimeoutSeconds}s</dd></div>
              <div><dt>Concurrent deliveries</dt><dd>{policy.webhookConcurrencyPerMerchant} / merchant</dd></div>
              <div><dt>Dead-letter retention</dt><dd>{policy.webhookDeliveryRetentionDays} days</dd></div>
            </dl>
            <div className="adm-form-actions">
              {canEditSettings ? <Button variant="ghost" onClick={() => setSigningOpen(true)}>Edit signing config</Button> : null}
              {canEditSettings ? <Button onClick={() => setRetryOpen(true)}>Edit retry policy</Button> : null}
            </div>
          </Card>

          <Card tone="mint">
            <CardHeader title="Subscribed event types" description="Events emitted to merchants by default." />
            <ul className="adm-toggle-list">
              {[
                "subscription.created",
                "subscription.updated",
                "subscription.canceled",
                "invoice.paid",
                "invoice.failed",
                "invoice.recovered",
                "payment.captured",
                "payment.refunded",
                "customer.card_updated"
              ].map((evt) => (
                <li key={evt} className="adm-toggle-row">
                  <input
                    type="checkbox"
                    checked={(policy.subscribedEventTypes ?? []).includes(evt)}
                    onChange={() => handleToggleEventType(evt)}
                  />
                  <code className="adm-code">{evt}</code>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ) : null}

      {tab === "security" ? (
        <section className="sp-panel-layout">
          <Card tone="mint">
            <CardHeader title="Authentication policy" description="Applies to every admin who can sign in to this console." />
            <ul className="adm-toggle-list">
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.enforcedMfa}
                  onChange={() => handleTogglePolicy("enforcedMfa", "Require MFA")}
                />
                <strong>Require MFA for all admins</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.ssoGoogleEnabled}
                  onChange={() => handleTogglePolicy("ssoGoogleEnabled", "Google SSO")}
                />
                <strong>SSO via Google Workspace</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.ipAllowlistEnabled}
                  onChange={() => handleTogglePolicy("ipAllowlistEnabled", "IP allowlist")}
                />
                <strong>IP allowlist</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.sessionTimeoutEnabled}
                  onChange={() => handleTogglePolicy("sessionTimeoutEnabled", "Session timeout")}
                />
                <strong>Session timeout after {policy.sessionLifetimeHours}h</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.blockNewCountriesEnabled}
                  onChange={() => handleTogglePolicy("blockNewCountriesEnabled", "Block new-country sign-ins")}
                />
                <strong>Block sign-ins from new countries</strong>
              </li>
            </ul>
          </Card>

          <Card>
            <CardHeader title="Password policy" description="Used for fallback password sign-in." />
            <div className="adm-form-grid">
              <Field label="Minimum length">
                <TextInput value={pwMinLength} onChange={(e) => setPwMinLength(e.target.value)} />
              </Field>
              <Field label="Rotation period (days)">
                <TextInput value={pwRotationDays} onChange={(e) => setPwRotationDays(e.target.value)} />
              </Field>
              <Field label="Disallow last N passwords">
                <TextInput value={pwHistoryCount} onChange={(e) => setPwHistoryCount(e.target.value)} />
              </Field>
              <Field label="Lockout after failed attempts">
                <TextInput value={pwLockoutThreshold} onChange={(e) => setPwLockoutThreshold(e.target.value)} />
              </Field>
            </div>
            {canEditSettings ? (
              <div className="adm-form-actions">
                <Button onClick={handleSaveSecurity} disabled={savingSecurity}>
                  {savingSecurity ? "Saving…" : "Save password policy"}
                </Button>
              </div>
            ) : null}
          </Card>

          <Card>
            <CardHeader title="API & webhook posture" description="Hardening for outbound and inbound network traffic." />
            <ul className="adm-toggle-list">
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.verifyHmacOnReceipts}
                  onChange={() => handleTogglePolicy("verifyHmacOnReceipts", "Verify HMAC on receipts")}
                />
                <strong>Verify HMAC on all webhook receipts</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.enforceTls13}
                  onChange={() => handleTogglePolicy("enforceTls13", "Enforce TLS 1.3")}
                />
                <strong>Enforce TLS 1.3 minimum</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.requireIdempotencyKey}
                  onChange={() => handleTogglePolicy("requireIdempotencyKey", "Require idempotency key")}
                />
                <strong>Reject requests without idempotency key</strong>
              </li>
              <li className="adm-toggle-row">
                <input
                  type="checkbox"
                  checked={policy.allowSelfSignedDevEndpoints}
                  onChange={() => handleTogglePolicy("allowSelfSignedDevEndpoints", "Allow self-signed dev endpoints")}
                />
                <strong>Allow self-signed merchant endpoints (dev only)</strong>
              </li>
            </ul>
          </Card>
        </section>
      ) : null}

      {tab === "data" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader title="Data retention" description="How long SubPilot keeps various record types." />
            <div className="adm-form-grid">
              <Field label="Audit log retention (days)">
                <TextInput value={auditRetentionDays} onChange={(e) => setAuditRetentionDays(e.target.value)} />
              </Field>
              <Field label="Webhook delivery retention (days)">
                <TextInput value={webhookRetentionDays} onChange={(e) => setWebhookRetentionDays(e.target.value)} />
              </Field>
              <Field label="Tokenized card retention (days)">
                <TextInput value={cardRetentionDays} onChange={(e) => setCardRetentionDays(e.target.value)} />
              </Field>
              <Field label="Customer profile retention">
                <SelectInput value={customerRetention} onChange={(e) => setCustomerRetention(e.target.value)}>
                  <option value="forever">Until deletion request</option>
                  <option value="2y">2 years after churn</option>
                  <option value="5y">5 years after churn</option>
                </SelectInput>
              </Field>
            </div>
            {canEditSettings ? (
              <div className="adm-form-actions">
                <Button onClick={handleSaveDataRetention} disabled={savingData}>
                  {savingData ? "Saving…" : "Save retention"}
                </Button>
              </div>
            ) : null}
          </Card>

          <Card tone="mint">
            <CardHeader title="Compliance" description="Where SubPilot is in scope and how to request reports." />
            <ul className="adm-compliance-list">
              <li><ShieldCheck size={14} aria-hidden="true" /> PCI-DSS SAQ-D (current)</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> SOC 2 Type II report — 2026 Q1</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> NDPR registered data controller</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> Customer data residency: Lagos · Frankfurt</li>
            </ul>
            <div className="adm-form-actions">
              <Button variant="ghost" onClick={() => handleExport("SOC 2 Type II report")}>Download SOC 2</Button>
              <Button
                variant="ghost"
                onClick={() =>
                  notify({
                    tone: "info",
                    title: "DPA requested",
                    description: "Our compliance team will email you the data processing agreement within 24 hours."
                  })
                }
              >
                Request DPA
              </Button>
            </div>
          </Card>

          <Card>
            <CardHeader title="Exports" description="One-off data extracts." />
            <ul className="adm-endpoint-list">
              <li className="adm-endpoint-row">
                <div><strong>Merchants snapshot</strong><small>CSV · all merchants and key risk metrics</small></div>
                <Button variant="ghost" onClick={() => handleExport("Merchants snapshot")}>Export</Button>
              </li>
              <li className="adm-endpoint-row">
                <div><strong>Audit log archive</strong><small>NDJSON · last 90 days</small></div>
                <Button variant="ghost" onClick={() => handleExport("Audit log archive")}>Export</Button>
              </li>
              <li className="adm-endpoint-row">
                <div><strong>Webhook deliveries</strong><small>NDJSON · failed only</small></div>
                <Button variant="ghost" onClick={() => handleExport("Webhook deliveries")}>Export</Button>
              </li>
            </ul>
          </Card>
        </section>
      ) : null}

      {tab === "branding" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader title="Customer-facing branding" description="Used on the hosted customer portal and email templates." />
            <div className="adm-form-grid">
              <Field label="Display name">
                <TextInput value={brandName} onChange={(e) => setBrandName(e.target.value)} />
              </Field>
              <Field label="Support email">
                <TextInput type="email" value={brandEmail} onChange={(e) => setBrandEmail(e.target.value)} />
              </Field>
              <Field label="Primary color">
                <TextInput value={brandPrimary} onChange={(e) => setBrandPrimary(e.target.value)} />
              </Field>
              <Field label="Accent color">
                <TextInput value={brandAccent} onChange={(e) => setBrandAccent(e.target.value)} />
              </Field>
            </div>
            <div className="adm-form-actions">
              {canEditSettings ? (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setBrandName(policy.brandDisplayName);
                    setBrandEmail(policy.brandSupportEmail);
                    setBrandPrimary(policy.brandPrimaryColor);
                    setBrandAccent(policy.brandAccentColor);
                    notify({ tone: "info", title: "Changes discarded", description: "Reverted to saved branding." });
                  }}
                  disabled={savingBranding}
                >
                  Discard
                </Button>
              ) : null}
              {canEditSettings ? (
                <Button onClick={handleSaveBranding} disabled={savingBranding}>
                  {savingBranding ? "Saving…" : "Save branding"}
                </Button>
              ) : null}
            </div>
          </Card>

          <Card tone="mint">
            <CardHeader title="Email templates" description="Override the defaults sent to merchant customers." />
            <ul className="adm-endpoint-list">
              <li className="adm-endpoint-row">
                <div><strong>Invoice receipt</strong><small>Sent on capture</small></div>
                <Badge tone="success">Default</Badge>
                <Button variant="ghost" onClick={() => handleEdit("Invoice receipt template")} disabled={!canEditSettings}>Edit</Button>
              </li>
              <li className="adm-endpoint-row">
                <div><strong>Failed payment</strong><small>Sent on dunning step 1</small></div>
                <Badge tone="success">Default</Badge>
                <Button variant="ghost" onClick={() => handleEdit("Failed payment template")} disabled={!canEditSettings}>Edit</Button>
              </li>
              <li className="adm-endpoint-row">
                <div><strong>Card expiring</strong><small>Sent 14 days before expiry</small></div>
                <Badge tone="info">Custom</Badge>
                <Button variant="ghost" onClick={() => handleEdit("Card expiring template")} disabled={!canEditSettings}>Edit</Button>
              </li>
            </ul>
          </Card>
        </section>
      ) : null}

      {tab === "audit" ? (
        <Card>
          <CardHeader
            title="Platform audit log"
            description="Every administrative action across SubPilot. Tamper-evident and exportable."
            action={
              <Button
                variant="ghost"
                icon={<RefreshCw size={14} />}
                onClick={() => {
                  void reloadAudit();
                  notify({
                    tone: "success",
                    title: "Audit log refreshed",
                    description: "Fetched the latest entries from the platform audit pipeline."
                  });
                }}
                disabled={auditLoading}
              >
                Refresh
              </Button>
            }
          />
          <div className="adm-form-grid" style={{ marginBottom: 12 }}>
            <Field label="Filter by category">
              <SelectInput
                value={auditCategory}
                onChange={(e) => setAuditCategory(e.target.value as AuditCategory | "")}
              >
                <option value="">All categories</option>
                <option value="merchant">Merchant</option>
                <option value="platform">Platform</option>
                <option value="team">Team</option>
                <option value="security">Security</option>
              </SelectInput>
            </Field>
          </div>
          {auditError ? (
            <p className="adm-muted" role="alert">{auditError}</p>
          ) : null}
          {!auditError && auditLoading && auditEntries.length === 0 ? (
            <p className="adm-muted">Loading audit log…</p>
          ) : null}
          {!auditError && !auditLoading && auditEntries.length === 0 ? (
            <p className="adm-muted">No audit entries match the current filter.</p>
          ) : null}
          <ul className="adm-timeline">
            {auditEntries.map((a) => (
              <li key={a.id} className="adm-timeline__item">
                <span className="adm-timeline__dot" aria-hidden="true" />
                <div>
                  <div className="adm-timeline__head">
                    <strong>{a.action}</strong>
                    <Badge tone={a.category === "security" ? "danger" : a.category === "merchant" ? "info" : a.category === "team" ? "teal" : "neutral"}>{a.category}</Badge>
                  </div>
                  <p>{a.detail}</p>
                  <small>{a.actor} · {formatTime(a.occurredAt)}{a.merchantId ? ` · ${a.merchantId}` : ""}</small>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {tab === "profile" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader title="Your profile" description="Visible to other SubPilot operators in the audit log." />
            <div className="adm-form-grid">
              <Field label="Full name">
                <TextInput value={profileName} onChange={(e) => setProfileName(e.target.value)} />
              </Field>
              <Field label="Work email">
                <TextInput type="email" value={profileEmail} onChange={(e) => setProfileEmail(e.target.value)} />
              </Field>
              <Field label="Role"><TextInput value={user?.role ?? ""} disabled readOnly /></Field>
              <Field label="User ID"><TextInput value={user?.id ?? ""} disabled readOnly /></Field>
            </div>
            <div className="adm-form-actions">
              <Button variant="ghost" onClick={handleDiscardProfile} disabled={savingProfile}>Discard</Button>
              <Button onClick={handleSaveProfile} disabled={savingProfile}>
                {savingProfile ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </Card>

          <Card tone="mint">
            <CardHeader title="Security" description="Hardening posture for this account." />
            <ul className="adm-compliance-list">
              <li><ShieldCheck size={14} aria-hidden="true" /> SSO via Google enforced</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> MFA: Authenticator app</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> 4 active sessions</li>
              <li><ShieldCheck size={14} aria-hidden="true" /> Last password rotation: 2026-04-01</li>
            </ul>
            <div className="adm-form-actions">
              <Button
                variant="ghost"
                onClick={() =>
                  notify({
                    tone: "info",
                    title: "Active sessions",
                    description: "4 active sessions found across web, CLI, and mobile."
                  })
                }
              >
                View sessions
              </Button>
              <Button
                onClick={() =>
                  notify({
                    tone: "success",
                    title: "Password rotation initiated",
                    description: "We've emailed you a secure rotation link. Active sessions stay valid until rotation completes."
                  })
                }
              >
                Rotate password
              </Button>
            </div>
          </Card>
        </section>
      ) : null}

      {/* Danger zone — Owners only */}
      {canEditSettings ? (
        <Card>
          <CardHeader
            title="Danger zone"
            description="These actions affect the entire SubPilot platform. Owners only."
            action={<Badge tone="danger">High blast radius</Badge>}
          />
          <div className="adm-danger-row">
            <div>
              <strong>Pause all webhook deliveries</strong>
              <p>Useful during incident response. Existing events queue for replay.</p>
            </div>
            <Button variant="danger" icon={<PauseCircle size={14} />} onClick={() => setPauseAllOpen(true)}>Pause all webhooks</Button>
          </div>
          <div className="adm-danger-row">
            <div>
              <strong>Enter platform read-only mode</strong>
              <p>Disables every write endpoint until manually lifted.</p>
            </div>
            <Button variant="danger" icon={<Pause size={14} />} onClick={handleReadOnlyMode}>Enable read-only</Button>
          </div>
        </Card>
      ) : null}

      {/* ---------------- Modals & Sheets ---------------- */}
      <Modal
        open={pauseAllOpen}
        title="Pause all outbound webhooks?"
        description="Every merchant will stop receiving events until you resume. Inbound API stays live."
        onClose={() => setPauseAllOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPauseAllOpen(false)}>Cancel</Button>
            <Button
              variant="danger"
              onClick={handlePauseAllWebhooks}
              icon={<PauseCircle size={14} />}
            >
              Pause everything
            </Button>
          </>
        }
      >
        <p className="adm-modal-warn"><AlertTriangle size={14} /> Use only during a confirmed incident. Customers see no UI change but webhook delivery latency will spike when resumed.</p>
        <Field label="Incident reference">
          <TextInput placeholder="INC-2026-07-05-…" />
        </Field>
      </Modal>

      <Modal
        open={rotateOpen}
        title="Rotate platform signing key"
        description="Generates a new platform-wide HMAC key. The previous key is honored during the grace window."
        onClose={() => setRotateOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRotateOpen(false)}>Cancel</Button>
            <Button
              onClick={handleRotateSigningKey}
              icon={<KeyRound size={14} />}
            >
              Rotate now
            </Button>
          </>
        }
      >
        <p className="adm-modal-warn"><ShieldAlert size={14} /> All merchants will see this in their developer console immediately.</p>
        <Field label="Grace period">
          <SelectInput defaultValue="48h">
            <option value="0">None (cut over immediately)</option>
            <option value="24h">24 hours</option>
            <option value="48h">48 hours</option>
            <option value="7d">7 days</option>
          </SelectInput>
        </Field>
        <Field label="Notify merchants via">
          <SegmentedControl
            label="Notification channel"
            value={rotateChannel}
            onChange={setRotateChannel}
            items={[
              { label: "Email", value: "email" },
              { label: "Webhook", value: "webhook" },
              { label: "Email + Webhook", value: "email-webhook" }
            ]}
          />
        </Field>
      </Modal>

      <Sheet
        open={retryOpen}
        title="Edit default retry policy"
        description="Applied to merchants that have not customized their own retry settings."
        onClose={() => setRetryOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRetryOpen(false)} disabled={savingPolicy}>Cancel</Button>
            <Button onClick={handleSaveRetryPolicy} disabled={savingPolicy}>
              {savingPolicy ? "Saving…" : "Save policy"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Retry attempts">
            <TextInput value={retryAttempts} onChange={(e) => setRetryAttempts(e.target.value)} />
          </Field>
          <Field label="Cooldown (hours)">
            <TextInput value={retryCooldown} onChange={(e) => setRetryCooldown(e.target.value)} />
          </Field>
          <Field label="Timeout (seconds)">
            <TextInput value={retryTimeout} onChange={(e) => setRetryTimeout(e.target.value)} />
          </Field>
          <Field label="Concurrent deliveries / merchant">
            <TextInput value={retryConcurrency} onChange={(e) => setRetryConcurrency(e.target.value)} />
          </Field>
        </div>
        <Field label="Backoff strategy">
          <SegmentedControl
            label="Backoff strategy"
            value={retryBackoff}
            onChange={setRetryBackoff}
            items={[
              { label: "Linear", value: "Linear" },
              { label: "Exponential", value: "Exponential" }
            ]}
          />
        </Field>
        <h3 className="adm-sheet-section">Dunning cadence</h3>
        <ul className="adm-toggle-list">
          <li className="adm-toggle-row">
            <input
              type="checkbox"
              checked={policy.dunningEmailD1}
              onChange={() => handleTogglePolicy("dunningEmailD1", "Email at D+1")}
            />
            <strong>Email at D+1</strong>
          </li>
          <li className="adm-toggle-row">
            <input
              type="checkbox"
              checked={policy.dunningEmailSmsD3}
              onChange={() => handleTogglePolicy("dunningEmailSmsD3", "Email + SMS at D+3")}
            />
            <strong>Email + SMS at D+3</strong>
          </li>
          <li className="adm-toggle-row">
            <input
              type="checkbox"
              checked={policy.dunningFinalNoticeD7}
              onChange={() => handleTogglePolicy("dunningFinalNoticeD7", "Final notice at D+7")}
            />
            <strong>Final notice at D+7</strong>
          </li>
          <li className="adm-toggle-row">
            <input
              type="checkbox"
              checked={policy.dunningAutoPauseD10}
              onChange={() => handleTogglePolicy("dunningAutoPauseD10", "Auto-pause at D+10")}
            />
            <strong>Auto-pause subscription at D+10</strong>
          </li>
        </ul>
      </Sheet>

      <Sheet
        open={signingOpen}
        title="Edit signing config"
        description="Header naming and verification posture for outbound webhooks."
        onClose={() => setSigningOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setSigningOpen(false)} disabled={savingSigning}>Cancel</Button>
            <Button onClick={handleSaveSigningConfig} disabled={savingSigning}>
              {savingSigning ? "Saving…" : "Save changes"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Signature header">
            <TextInput value={signingHeader} onChange={(e) => setSigningHeader(e.target.value)} />
          </Field>
          <Field label="Algorithm">
            <SelectInput value={signingAlgorithm} onChange={(e) => setSigningAlgorithm(e.target.value)}>
              <option value="hmac-sha256">HMAC-SHA256</option>
              <option value="hmac-sha512">HMAC-SHA512</option>
              <option value="ed25519">Ed25519</option>
            </SelectInput>
          </Field>
          <Field label="Timestamp tolerance (seconds)">
            <TextInput value={signingTolerance} onChange={(e) => setSigningTolerance(e.target.value)} />
          </Field>
          <Field label="Replay window (minutes)">
            <TextInput value={signingReplayWindow} onChange={(e) => setSigningReplayWindow(e.target.value)} />
          </Field>
        </div>
      </Sheet>

      <Sheet
        open={!!adapterFor}
        title={adapterFor ? `Configure ${adapterFor.name}` : ""}
        description={adapterFor?.role ?? ""}
        onClose={() => setAdapterFor(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdapterFor(null)}>Cancel</Button>
            <Button onClick={handleSaveAdapter}>
              Save adapter
            </Button>
          </>
        }
      >
        {adapterFor ? (
          <>
            <div className="adm-form-grid">
              <Field label="Display name">
                <TextInput
                  value={adapterFor.name}
                  onChange={(e) => setAdapterFor({ ...adapterFor, name: e.target.value })}
                />
              </Field>
              <Field label="Region">
                <TextInput
                  value={adapterFor.region}
                  onChange={(e) => setAdapterFor({ ...adapterFor, region: e.target.value })}
                />
              </Field>
              <Field label="Failover trigger">
                <TextInput
                  value={adapterFor.failoverTrigger}
                  onChange={(e) => setAdapterFor({ ...adapterFor, failoverTrigger: e.target.value })}
                />
              </Field>
              <Field label="Status">
                <SelectInput
                  value={adapterFor.status}
                  onChange={(e) => setAdapterFor({ ...adapterFor, status: e.target.value })}
                >
                  <option>Operational</option>
                  <option>Monitoring</option>
                  <option>Disabled</option>
                </SelectInput>
              </Field>
            </div>
          </>
        ) : null}
      </Sheet>
    </>
  );
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}
