import { useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Checkbox,
  DataTable,
  Field,
  Modal,
  Pagination,
  SegmentedControl,
  SelectInput,
  Sheet,
  Tabs,
  TextInput,
  Toggle,
  type DataTableColumn
} from "@subpilot/ui";
import {
  AlertTriangle,
  Building2,
  Crown,
  Download,
  LogOut,
  Mail,
  Pause,
  Plus,
  Save,
  Trash2,
  XOctagon
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { formatRelative } from "../data/selectors";
import { isApiError } from "../api/client";
import {
  closeWorkspace,
  exportWorkspaceData,
  forceWorkspaceSignOut,
  transferWorkspaceOwnership
} from "../api/settings";
import type { AuditEvent, DunningTemplate, MerchantOrg } from "../data/seed";

type TabKey =
  | "organization"
  | "branding"
  | "billing"
  | "plans"
  | "dunning"
  | "notifications"
  | "security"
  | "portal"
  | "audit"
  | "danger";

const TAB_BY_HASH: Record<string, TabKey> = {
  "#organization": "organization",
  "#branding": "branding",
  "#billing": "billing",
  "#plans": "plans",
  "#dunning": "dunning",
  "#notifications": "notifications",
  "#security": "security",
  "#portal": "portal",
  "#audit": "audit",
  "#danger": "danger"
};

interface PayoutBankState {
  bank: string;
  accountNumber: string;
  descriptor: string;
}

interface TransferState {
  newOwnerEmail: string;
}

interface CloseWorkspaceState {
  confirmText: string;
}

export function SettingsPage() {
  const { org, settings, teamMembers, auditEvents, updateOrg, updateSettings, updateDunningSettings, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canManageDunning = can("manage_dunning_policies");
  const canForceSignout = can("force_workspace_signout");
  const canTransferOwnership = can("transfer_workspace_ownership");
  const canCloseWorkspace = can("close_workspace");
  const canExportData = can("export_workspace_data");
  const canViewAudit = can("view_audit_logs");
  const canSeeDangerZone = canTransferOwnership || canCloseWorkspace || canExportData;

  const [tab, setTab] = useState<TabKey>(() => {
    if (typeof window !== "undefined") {
      const hashTab = TAB_BY_HASH[window.location.hash];
      if (hashTab) return hashTab;
    }
    return "organization";
  });

  // Track hash changes (e.g. clicking "Configure dunning rules" from Recovery).
  useEffect(() => {
    const handler = () => {
      const next = TAB_BY_HASH[window.location.hash];
      if (next) setTab(next);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  // Local edit buffers — saved via Save button.
  const [orgDraft, setOrgDraft] = useState<MerchantOrg>(org);
  const [brandingDraft, setBrandingDraft] = useState(settings.branding);
  const [planDefaultsDraft, setPlanDefaultsDraft] = useState(settings.planDefaults);
  const [dunningDraft, setDunningDraft] = useState(settings.dunning);
  const [notificationsDraft, setNotificationsDraft] = useState(settings.notifications);
  const [securityDraft, setSecurityDraft] = useState(settings.security);
  const [portalDraft, setPortalDraft] = useState(settings.portal);
  const [templates, setTemplates] = useState<DunningTemplate[]>(settings.dunningTemplates);
  const [editingTemplate, setEditingTemplate] = useState<DunningTemplate | null>(null);
  const [payoutOpen, setPayoutOpen] = useState<PayoutBankState | null>(null);
  const [newIp, setNewIp] = useState("");
  const [transferOpen, setTransferOpen] = useState<TransferState | null>(null);
  const [closeOpen, setCloseOpen] = useState<CloseWorkspaceState | null>(null);
  const [saving, setSaving] = useState<
    | "organization"
    | "branding"
    | "payouts"
    | "plans"
    | "dunning"
    | "notifications"
    | "security"
    | "portal"
    | "export"
    | "sessions"
    | "ownership"
    | "close"
    | null
  >(null);

  useEffect(() => {
    setOrgDraft(org);
    setBrandingDraft(settings.branding);
    setPlanDefaultsDraft(settings.planDefaults);
    setDunningDraft(settings.dunning);
    setTemplates(settings.dunningTemplates);
    setNotificationsDraft(settings.notifications);
    setSecurityDraft(settings.security);
    setPortalDraft(settings.portal);
  }, [org, settings]);

  // ---------- Organization ----------
  async function saveOrganization() {
    if (!orgDraft.legalName.trim() || !orgDraft.tradingName.trim()) {
      notify({ tone: "warning", title: "Missing details", description: "Legal name and trading name are required." });
      return;
    }
    setSaving("organization");
    try {
      await updateOrg({
        legalName: orgDraft.legalName.trim(),
        tradingName: orgDraft.tradingName.trim(),
        country: orgDraft.country,
        timezone: orgDraft.timezone,
        taxId: orgDraft.taxId,
        statementDescriptor: orgDraft.statementDescriptor
      });
      logAuditEvent({ actor: "You", action: "Updated organization profile", target: orgDraft.legalName });
      notify({ tone: "success", title: "Organization saved", description: "Your workspace details are up to date." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save organization",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Branding ----------
  async function saveBranding() {
    if (!/^[a-z0-9-]+$/.test(brandingDraft.portalSubdomain)) {
      notify({ tone: "warning", title: "Invalid subdomain", description: "Use lowercase letters, numbers, and hyphens only." });
      return;
    }
    setSaving("branding");
    try {
      await updateSettings({ branding: brandingDraft });
      logAuditEvent({ actor: "You", action: "Updated branding", target: "Settings → Branding" });
      notify({ tone: "success", title: "Branding saved", description: `Portal lives at ${brandingDraft.portalSubdomain}.subpilot.dev` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save branding",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Billing & payouts ----------
  function openPayoutEdit() {
    setPayoutOpen({
      bank: settings.payouts.bank,
      accountNumber: settings.payouts.accountNumber,
      descriptor: settings.payouts.descriptor
    });
  }
  async function submitPayoutEdit() {
    if (!payoutOpen) return;
    const ok = await confirm({
      title: "Verify with micro-deposit?",
      description: "We'll send a tiny test deposit to confirm the new account before switching payouts.",
      confirmLabel: "Send micro-deposit"
    });
    if (!ok) return;
    setSaving("payouts");
    try {
      await updateSettings({
        payouts: { ...settings.payouts, bank: payoutOpen.bank, accountNumber: payoutOpen.accountNumber, descriptor: payoutOpen.descriptor }
      });
      logAuditEvent({ actor: "You", action: "Updated payout bank", target: payoutOpen.bank });
      notify({ tone: "success", title: "Payout bank updated", description: `Micro-deposit sent to ${payoutOpen.bank} •••${payoutOpen.accountNumber.slice(-4)}.` });
      setPayoutOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update payout bank",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  async function saveSettlement(frequency: MerchantOrg["settlementFrequency"]) {
    setSaving("payouts");
    try {
      await updateSettings({ payouts: { ...settings.payouts, settlementFrequency: frequency } });
      logAuditEvent({ actor: "You", action: `Set settlement to ${frequency}`, target: "Settings → Billing & payouts" });
      notify({ tone: "success", title: "Settlement schedule saved", description: `Now ${frequency}.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save settlement schedule",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  async function handlePausePayouts() {
    if (settings.payouts.paused) {
      setSaving("payouts");
      try {
        await updateSettings({ payouts: { ...settings.payouts, paused: false } });
        logAuditEvent({ actor: "You", action: "Resumed payouts", target: "Settings → Billing & payouts" });
        notify({ tone: "success", title: "Payouts resumed", description: "Settlements will run on the next cycle." });
      } catch (err) {
        notify({
          tone: "danger",
          title: "Could not resume payouts",
          description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
        });
      } finally {
        setSaving(null);
      }
      return;
    }
    const ok = await confirm({
      destructive: true,
      title: "Pause all payouts?",
      description: "Settlements will stop until you resume. Charges continue, but funds remain in the SubPilot balance.",
      confirmLabel: "Pause payouts"
    });
    if (!ok) return;
    setSaving("payouts");
    try {
      await updateSettings({ payouts: { ...settings.payouts, paused: true } });
      logAuditEvent({ actor: "You", action: "Paused payouts", target: "Settings → Billing & payouts" });
      notify({ tone: "warning", title: "Payouts paused", description: "Resume anytime from this page." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not pause payouts",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Plan defaults ----------
  async function savePlanDefaults() {
    setSaving("plans");
    try {
      await updateSettings({ planDefaults: planDefaultsDraft });
      logAuditEvent({ actor: "You", action: "Updated plan defaults", target: "Settings → Plan defaults" });
      notify({ tone: "success", title: "Plan defaults saved", description: "New plans inherit these values." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save plan defaults",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Dunning ----------
  function setSchedulePreset(preset: "gentle" | "standard" | "aggressive") {
    const next = preset === "gentle" ? [24, 72, 168] : preset === "aggressive" ? [3, 12, 24, 48] : [12, 24, 72];
    setDunningDraft({ ...dunningDraft, schedule: next });
  }
  async function saveDunning() {
    setSaving("dunning");
    try {
      await updateDunningSettings(dunningDraft);
      logAuditEvent({ actor: "You", action: "Updated dunning rules", target: "Settings → Dunning rules" });
      notify({ tone: "success", title: "Dunning saved", description: `Retry schedule: ${dunningDraft.schedule.join(", ")}h.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save dunning",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  function openTemplateEdit(tpl: DunningTemplate) {
    setEditingTemplate({ ...tpl });
  }
  async function saveTemplate() {
    if (!editingTemplate) return;
    const nextTemplates = templates.map((t) => (t.id === editingTemplate.id ? editingTemplate : t));
    setSaving("dunning");
    try {
      await updateSettings({ dunningTemplates: nextTemplates });
      setTemplates(nextTemplates);
      logAuditEvent({ actor: "You", action: "Updated dunning template", target: editingTemplate.label });
      notify({ tone: "success", title: "Template saved", description: editingTemplate.label });
      setEditingTemplate(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save template",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Notifications ----------
  function toggleNotification(group: string, channel: string) {
    setNotificationsDraft((prev) => ({
      ...prev,
      [group]: { ...prev[group], [channel]: !prev[group][channel] }
    }));
  }
  async function saveNotifications() {
    setSaving("notifications");
    try {
      await updateSettings({ notifications: notificationsDraft });
      logAuditEvent({ actor: "You", action: "Updated notifications", target: "Settings → Notifications" });
      notify({ tone: "success", title: "Notifications saved", description: "Channel preferences updated." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save notifications",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Security ----------
  async function saveSecurity() {
    setSaving("security");
    try {
      await updateSettings({ security: securityDraft });
      logAuditEvent({ actor: "You", action: "Updated security settings", target: "Settings → Security" });
      notify({ tone: "success", title: "Security saved", description: "Workspace security policy updated." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save security",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  function addIp() {
    if (!/^(\d{1,3}\.){3}\d{1,3}(\/(3[0-2]|[12]?\d))?$/.test(newIp)) {
      notify({ tone: "warning", title: "Invalid IP/CIDR", description: "Enter a valid IPv4 address or CIDR block." });
      return;
    }
    setSecurityDraft({ ...securityDraft, ipAllowlist: [...securityDraft.ipAllowlist, newIp] });
    logAuditEvent({ actor: "You", action: "Added IP to allowlist", target: newIp });
    notify({ tone: "success", title: "IP added", description: `${newIp} can now access the dashboard.` });
    setNewIp("");
  }
  async function removeIp(ip: string) {
    const ok = await confirm({
      destructive: true,
      title: `Remove ${ip} from allowlist?`,
      description: "Anyone signing in from this IP will be blocked.",
      confirmLabel: "Remove"
    });
    if (!ok) return;
    setSecurityDraft({ ...securityDraft, ipAllowlist: securityDraft.ipAllowlist.filter((i) => i !== ip) });
    logAuditEvent({ actor: "You", action: "Removed IP from allowlist", target: ip });
    notify({ tone: "warning", title: "IP removed", description: ip });
  }
  async function handleForceSignOut() {
    const ok = await confirm({
      destructive: true,
      title: "Force sign-out everyone?",
      description: "Every active session across the workspace will be invalidated. People will have to sign in again.",
      confirmLabel: "Sign out all sessions"
    });
    if (!ok) return;
    setSaving("sessions");
    try {
      const result = await forceWorkspaceSignOut();
      logAuditEvent({ actor: "You", action: "Forced sign-out for all sessions", target: "Workspace" });
      notify({
        tone: "warning",
        title: "All sessions ended",
        description: `${result.sessionsInvalidated} active session${result.sessionsInvalidated === 1 ? "" : "s"} invalidated. Redirecting to sign in.`
      });
      window.setTimeout(() => {
        window.location.assign("/sign-in");
      }, 900);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not force sign-out",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
      setSaving(null);
    }
  }

  // ---------- Portal ----------
  async function savePortal() {
    setSaving("portal");
    try {
      await updateSettings({ portal: portalDraft });
      logAuditEvent({ actor: "You", action: "Updated customer portal settings", target: "Settings → Customer portal" });
      notify({ tone: "success", title: "Portal saved", description: "Customer-facing portal updated." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save portal",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  // ---------- Audit log ----------
  const [auditQuery, setAuditQuery] = useState("");
  const filteredAudit = useMemo(() => {
    const q = auditQuery.trim().toLowerCase();
    if (!q) return auditEvents;
    return auditEvents.filter((e) => `${e.actor} ${e.action} ${e.target}`.toLowerCase().includes(q));
  }, [auditEvents, auditQuery]);
  const auditPager = usePagination(filteredAudit, 12, "events");
  const auditColumns: DataTableColumn<AuditEvent>[] = [
    { key: "actor", header: "Actor", render: (e) => e.actor },
    { key: "action", header: "Action", render: (e) => e.action },
    { key: "target", header: "Target", render: (e) => <span className="mer-muted">{e.target}</span> },
    { key: "ip", header: "IP", render: (e) => <code style={{ fontSize: 12 }}>{e.ipAddress}</code> },
    { key: "when", header: "When", render: (e) => formatRelative(e.occurredAt) }
  ];

  // ---------- Danger zone ----------
  async function exportAllData() {
    setSaving("export");
    try {
      const exportRequest = await exportWorkspaceData();
      logAuditEvent({ actor: "You", action: "Requested workspace export", target: exportRequest.id });
      notify({
        tone: "info",
        title: "Export queued",
        description: `We'll email ${exportRequest.delivery_email} when ${exportRequest.id} is ready.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not queue export",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  function openTransfer() {
    setTransferOpen({ newOwnerEmail: "" });
  }
  async function submitTransfer() {
    if (!transferOpen) return;
    const target = teamMembers.find((m) => m.email.toLowerCase() === transferOpen.newOwnerEmail.trim().toLowerCase());
    if (!target) {
      notify({ tone: "warning", title: "No matching teammate", description: "The new owner must already be on the team." });
      return;
    }
    const ok = await confirm({
      destructive: true,
      title: "Transfer ownership?",
      description: `${target.name} will become the new Owner. You'll be downgraded to Admin. This cannot be undone from this screen.`,
      confirmLabel: "Transfer ownership"
    });
    if (!ok) return;
    setSaving("ownership");
    try {
      await transferWorkspaceOwnership(target.email);
      logAuditEvent({ actor: "You", action: "Transferred ownership", target: target.email });
      notify({ tone: "warning", title: "Ownership transferred", description: `${target.name} is now Owner.` });
      setTransferOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not transfer ownership",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }
  function openClose() {
    setCloseOpen({ confirmText: "" });
  }
  async function submitClose() {
    if (!closeOpen) return;
    if (closeOpen.confirmText !== org.tradingName) {
      notify({ tone: "warning", title: "Confirmation mismatch", description: `Type "${org.tradingName}" exactly to confirm.` });
      return;
    }
    const ok = await confirm({
      destructive: true,
      title: "Close workspace permanently?",
      description: "All data, subscriptions, and customers will be deleted. This is irreversible.",
      confirmLabel: "Close workspace"
    });
    if (!ok) return;
    setSaving("close");
    try {
      await closeWorkspace(closeOpen.confirmText);
      logAuditEvent({ actor: "You", action: "Closed workspace", target: org.tradingName });
      notify({ tone: "warning", title: "Workspace closed", description: "You'll be signed out shortly." });
      setCloseOpen(null);
      window.setTimeout(() => {
        window.location.assign("/sign-in");
      }, 800);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not close workspace",
        description: isApiError(err) ? err.reason : "Try again after refreshing the dashboard."
      });
    } finally {
      setSaving(null);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        description="Configure your organization, branding, billing, recovery, security, and more."
      />

      <Card>
        <Tabs
          value={tab}
          onChange={(v) => setTab(v as TabKey)}
          items={[
            { label: "Organization", value: "organization" },
            { label: "Branding", value: "branding" },
            { label: "Billing & payouts", value: "billing" },
            { label: "Plan defaults", value: "plans" },
            ...(canManageDunning ? [{ label: "Dunning", value: "dunning" }] : []),
            { label: "Notifications", value: "notifications" },
            { label: "Security", value: "security" },
            { label: "Customer portal", value: "portal" },
            ...(canViewAudit ? [{ label: "Audit log", value: "audit" }] : []),
            ...(canSeeDangerZone ? [{ label: "Danger zone", value: "danger" }] : [])
          ]}
        />

        {/* ---------- Organization ---------- */}
        {tab === "organization" ? (
          <div className="mer-section">
            <CardHeader title="Organization profile" description="Legal and contact details that appear on invoices and receipts." />
            <div className="sp-grid sp-grid-2">
              <Field label="Legal name">
                <TextInput value={orgDraft.legalName} onChange={(e) => setOrgDraft({ ...orgDraft, legalName: e.target.value })} />
              </Field>
              <Field label="Trading name">
                <TextInput value={orgDraft.tradingName} onChange={(e) => setOrgDraft({ ...orgDraft, tradingName: e.target.value })} />
              </Field>
              <Field label="Country">
                <SelectInput value={orgDraft.country} onChange={(e) => setOrgDraft({ ...orgDraft, country: e.target.value })}>
                  <option value="Nigeria">Nigeria</option>
                  <option value="Kenya">Kenya</option>
                  <option value="Ghana">Ghana</option>
                  <option value="South Africa">South Africa</option>
                </SelectInput>
              </Field>
              <Field label="Timezone">
                <SelectInput value={orgDraft.timezone} onChange={(e) => setOrgDraft({ ...orgDraft, timezone: e.target.value })}>
                  <option value="Africa/Lagos">Africa/Lagos</option>
                  <option value="Africa/Nairobi">Africa/Nairobi</option>
                  <option value="Africa/Accra">Africa/Accra</option>
                  <option value="Africa/Johannesburg">Africa/Johannesburg</option>
                </SelectInput>
              </Field>
              <Field label="Tax ID">
                <TextInput value={orgDraft.taxId} onChange={(e) => setOrgDraft({ ...orgDraft, taxId: e.target.value })} />
              </Field>
              <Field label="Statement descriptor" hint="Up to 22 chars · appears on bank statements.">
                <TextInput value={orgDraft.statementDescriptor} maxLength={22} onChange={(e) => setOrgDraft({ ...orgDraft, statementDescriptor: e.target.value })} />
              </Field>
            </div>
            <div>
              <Button onClick={saveOrganization} icon={<Save size={14} />} disabled={saving === "organization"}>
                {saving === "organization" ? "Saving..." : "Save organization"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Branding ---------- */}
        {tab === "branding" ? (
          <div className="mer-section">
            <CardHeader title="Branding" description="Customer portal subdomain, logo, and primary color." />
            <div className="sp-grid sp-grid-2">
              <Field label="Primary color" hint="Hex value used in the portal hero and email buttons.">
                <span>
                  <span className="mer-color-swatch" style={{ background: brandingDraft.primaryColor }} />
                  <TextInput
                    value={brandingDraft.primaryColor}
                    onChange={(e) => setBrandingDraft({ ...brandingDraft, primaryColor: e.target.value })}
                  />
                </span>
              </Field>
              <Field label="Portal subdomain" hint="{slug}.subpilot.dev — checked for availability when saved.">
                <TextInput
                  value={brandingDraft.portalSubdomain}
                  onChange={(e) => setBrandingDraft({ ...brandingDraft, portalSubdomain: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Logo URL (optional)">
              <TextInput
                placeholder="https://cdn.example.com/logo.png"
                value={brandingDraft.logoUrl ?? ""}
                onChange={(e) => setBrandingDraft({ ...brandingDraft, logoUrl: e.target.value || null })}
              />
            </Field>
            <div>
              <Button onClick={saveBranding} icon={<Save size={14} />}>Save branding</Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Billing & payouts ---------- */}
        {tab === "billing" ? (
          <div className="mer-section">
            <CardHeader title="Billing & payouts" description="Where your settlements land and how often." />
            <div className="mer-totals">
              <div className="mer-totals__row"><span>Bank</span><strong>{settings.payouts.bank}</strong></div>
              <div className="mer-totals__row"><span>Account</span><strong>•••• {settings.payouts.accountNumber.slice(-4)}</strong></div>
              <div className="mer-totals__row"><span>Descriptor</span><strong>{settings.payouts.descriptor}</strong></div>
              <div className="mer-totals__row"><span>Settlement</span>
                <SegmentedControl
                  value={settings.payouts.settlementFrequency}
                  onChange={(v) => saveSettlement(v as MerchantOrg["settlementFrequency"])}
                  label="Settlement frequency"
                  items={[
                    { label: "Daily", value: "daily" },
                    { label: "Weekly", value: "weekly" },
                    { label: "Monthly", value: "monthly" }
                  ]}
                />
              </div>
              <div className="mer-totals__row"><span>Status</span>
                <Badge tone={settings.payouts.paused ? "warning" : "success"}>{settings.payouts.paused ? "Paused" : "Active"}</Badge>
              </div>
            </div>
            <div className="mer-row-actions">
              <Button variant="secondary" icon={<Building2 size={14} />} onClick={openPayoutEdit}>Edit payout bank</Button>
              <Button variant={settings.payouts.paused ? "primary" : "danger"} icon={<Pause size={14} />} onClick={handlePausePayouts}>
                {settings.payouts.paused ? "Resume payouts" : "Pause payouts"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Plan defaults ---------- */}
        {tab === "plans" ? (
          <div className="mer-section">
            <CardHeader title="Plan defaults" description="Defaults applied to every new plan unless overridden." />
            <div className="sp-grid sp-grid-2">
              <Field label="Default trial (days)">
                <TextInput
                  type="number"
                  min={0}
                  max={90}
                  value={String(planDefaultsDraft.trialDays)}
                  onChange={(e) => setPlanDefaultsDraft({ ...planDefaultsDraft, trialDays: Number(e.target.value) || 0 })}
                />
              </Field>
              <Field label="Currency">
                <SelectInput
                  value={planDefaultsDraft.currency}
                  onChange={(e) => setPlanDefaultsDraft({ ...planDefaultsDraft, currency: e.target.value as MerchantOrg["currency"] })}
                >
                  <option value="NGN">NGN — Nigerian Naira</option>
                  <option value="USD">USD — US Dollar</option>
                  <option value="GBP">GBP — Pound Sterling</option>
                  <option value="KES">KES — Kenyan Shilling</option>
                </SelectInput>
              </Field>
              <Field label="Proration">
                <SegmentedControl
                  value={planDefaultsDraft.proration}
                  onChange={(v) => setPlanDefaultsDraft({ ...planDefaultsDraft, proration: v as "create_proration" | "none" })}
                  label="Proration policy"
                  items={[
                    { label: "Prorate changes", value: "create_proration" },
                    { label: "No proration", value: "none" }
                  ]}
                />
              </Field>
              <Field label="Tax behavior">
                <SegmentedControl
                  value={planDefaultsDraft.taxBehavior}
                  onChange={(v) => setPlanDefaultsDraft({ ...planDefaultsDraft, taxBehavior: v as "exclusive" | "inclusive" })}
                  label="Tax behavior"
                  items={[
                    { label: "Exclusive", value: "exclusive" },
                    { label: "Inclusive", value: "inclusive" }
                  ]}
                />
              </Field>
            </div>
            <div>
              <Button onClick={savePlanDefaults} icon={<Save size={14} />}>Save plan defaults</Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Dunning ---------- */}
        {tab === "dunning" ? (
          <div className="mer-section" id="dunning">
            <CardHeader title="Dunning rules" description="How aggressively SubPilot retries failed charges before giving up." />
            <Field label="Retry preset">
              <SegmentedControl
                value={presetFor(dunningDraft.schedule)}
                onChange={(v) => setSchedulePreset(v as "gentle" | "standard" | "aggressive")}
                label="Retry preset"
                items={[
                  { label: "Gentle", value: "gentle" },
                  { label: "Standard", value: "standard" },
                  { label: "Aggressive", value: "aggressive" }
                ]}
              />
            </Field>
            <Field label="Custom schedule (hours, comma separated)">
              <TextInput
                value={dunningDraft.schedule.join(", ")}
                onChange={(e) => {
                  const parts = e.target.value.split(",").map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n >= 0);
                  setDunningDraft({ ...dunningDraft, schedule: parts });
                }}
              />
            </Field>
            <div className="sp-grid sp-grid-2">
              <Field label="Max attempts">
                <TextInput type="number" min={1} max={10} value={String(dunningDraft.maxAttempts)} onChange={(e) => setDunningDraft({ ...dunningDraft, maxAttempts: Number(e.target.value) || 1 })} />
              </Field>
              <Field label="Grace days before final action">
                <TextInput type="number" min={0} max={30} value={String(dunningDraft.graceDays)} onChange={(e) => setDunningDraft({ ...dunningDraft, graceDays: Number(e.target.value) || 0 })} />
              </Field>
            </div>
            <Field label="Final action when retries exhaust">
              <SegmentedControl
                value={dunningDraft.finalAction}
                onChange={(v) => setDunningDraft({ ...dunningDraft, finalAction: v as "cancel" | "uncollectible" })}
                label="Final action"
                items={[
                  { label: "Cancel subscription", value: "cancel" },
                  { label: "Mark uncollectible", value: "uncollectible" }
                ]}
              />
            </Field>
            <CardHeader title="Email templates" description="Edit the messages sent to customers during dunning." />
            <ul className="mer-portal-history">
              {templates.map((t) => (
                <li key={t.id}>
                  <div>
                    <strong>{t.label}</strong>
                    <small>{t.body.slice(0, 80)}…</small>
                  </div>
                  <span />
                  <Button variant="ghost" onClick={() => openTemplateEdit(t)}>Edit</Button>
                </li>
              ))}
            </ul>
            {canManageDunning ? (
              <div>
                <Button onClick={saveDunning} icon={<Save size={14} />} disabled={saving === "dunning"}>
                  {saving === "dunning" ? "Saving..." : "Save dunning rules"}
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* ---------- Notifications ---------- */}
        {tab === "notifications" ? (
          <div className="mer-section">
            <CardHeader title="Notifications" description="Toggle channels for each event group." />
            <div className="mer-totals">
              <div className="mer-totals__row"><strong>Group</strong><strong style={{ display: "flex", gap: 32 }}><span>Email</span><span>SMS</span><span>Slack</span></strong></div>
              {Object.entries(notificationsDraft).map(([group, channels]) => (
                <div key={group} className="mer-totals__row">
                  <span style={{ textTransform: "capitalize" }}>{group}</span>
                  <span style={{ display: "flex", gap: 24 }}>
                    {(["email", "sms", "slack"] as const).map((ch) => (
                      <Checkbox
                        key={ch}
                        label=""
                        checked={!!channels[ch]}
                        onChange={() => toggleNotification(group, ch)}
                      />
                    ))}
                  </span>
                </div>
              ))}
            </div>
            <div>
              <Button onClick={saveNotifications} icon={<Save size={14} />}>Save notifications</Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Security ---------- */}
        {tab === "security" ? (
          <div className="mer-section">
            <CardHeader title="Security" description="MFA enforcement, IP allowlist, and session policy." />
            <Toggle
              label="Require MFA for all team members"
              description="New invites must enrol before accessing the dashboard."
              checked={securityDraft.requireMfa}
              onChange={(v) => setSecurityDraft({ ...securityDraft, requireMfa: v })}
            />
            <Field label="Session timeout (minutes)" hint="Active sessions sign out after this period of idle time.">
              <TextInput type="number" min={5} max={1440} value={String(securityDraft.sessionTimeoutMinutes)} onChange={(e) => setSecurityDraft({ ...securityDraft, sessionTimeoutMinutes: Number(e.target.value) || 60 })} />
            </Field>
            <CardHeader title="IP allowlist" description="Empty list allows access from anywhere. Add at least one to restrict." />
            <div className="sp-form-grid">
              <span style={{ display: "flex", gap: 8 }}>
                <TextInput placeholder="102.89.0.0/16" value={newIp} onChange={(e) => setNewIp(e.target.value)} />
                <Button variant="secondary" icon={<Plus size={14} />} onClick={addIp}>Add</Button>
              </span>
              {securityDraft.ipAllowlist.length === 0 ? (
                <p className="mer-empty">No restrictions — anyone with valid credentials can sign in.</p>
              ) : (
                securityDraft.ipAllowlist.map((ip) => (
                  <div key={ip} className="mer-allowlist-row">
                    <span>{ip}</span>
                    <Button variant="ghost" icon={<Trash2 size={14} />} onClick={() => removeIp(ip)}>Remove</Button>
                  </div>
                ))
              )}
            </div>
            <div className="mer-row-actions">
              <Button onClick={saveSecurity} icon={<Save size={14} />}>Save security</Button>
              {canForceSignout ? (
                <Button
                  variant="danger"
                  icon={<LogOut size={14} />}
                  onClick={handleForceSignOut}
                  disabled={saving === "sessions"}
                >
                  {saving === "sessions" ? "Signing out..." : "Force sign-out everyone"}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* ---------- Customer portal ---------- */}
        {tab === "portal" ? (
          <div className="mer-section">
            <CardHeader title="Customer portal" description="Control what customers can do from their self-service portal." />
            <Toggle label="Allow cancel subscription" checked={portalDraft.allowCancel} onChange={(v) => setPortalDraft({ ...portalDraft, allowCancel: v })} />
            <Toggle label="Allow pause subscription" checked={portalDraft.allowPause} onChange={(v) => setPortalDraft({ ...portalDraft, allowPause: v })} />
            <Toggle label="Allow change plan" checked={portalDraft.allowChangePlan} onChange={(v) => setPortalDraft({ ...portalDraft, allowChangePlan: v })} />
            <div className="sp-grid sp-grid-2">
              <Field label="Success URL" hint="Where customers are sent after a successful action.">
                <TextInput value={portalDraft.successUrl} onChange={(e) => setPortalDraft({ ...portalDraft, successUrl: e.target.value })} />
              </Field>
              <Field label="Cancel URL" hint="Where they go after cancelling.">
                <TextInput value={portalDraft.cancelUrl} onChange={(e) => setPortalDraft({ ...portalDraft, cancelUrl: e.target.value })} />
              </Field>
            </div>
            <div>
              <Button onClick={savePortal} icon={<Save size={14} />}>Save portal</Button>
            </div>
          </div>
        ) : null}

        {/* ---------- Audit log ---------- */}
        {tab === "audit" ? (
          <div className="mer-section">
            <CardHeader title="Audit log" description="Read-only record of every action taken on this workspace." />
            <Field label="Filter">
              <TextInput placeholder="Search actor, action or target" value={auditQuery} onChange={(e) => setAuditQuery(e.target.value)} />
            </Field>
            <DataTable columns={auditColumns} rows={auditPager.slice} getRowKey={(e) => e.id} emptyText="No audit events match." />
            <Pagination page={auditPager.page} pageCount={auditPager.pageCount} onPageChange={auditPager.setPage} totalLabel={auditPager.totalLabel} />
          </div>
        ) : null}

        {/* ---------- Danger zone ---------- */}
        {tab === "danger" && canSeeDangerZone ? (
          <div className="mer-section">
            <CardHeader title="Danger zone" description="Irreversible actions. Read each one carefully before confirming." />
            <div className="mer-totals">
              {canExportData ? (
                <div className="mer-totals__row">
                  <span><strong>Export workspace data</strong><br /><small>JSON dump of every entity.</small></span>
                  <Button
                    variant="secondary"
                    icon={<Download size={14} />}
                    onClick={exportAllData}
                    disabled={saving === "export"}
                  >
                    {saving === "export" ? "Queueing..." : "Export"}
                  </Button>
                </div>
              ) : null}
              {canTransferOwnership ? (
                <div className="mer-totals__row">
                  <span><strong>Transfer ownership</strong><br /><small>Hand the workspace to another teammate.</small></span>
                  <Button variant="danger" icon={<Crown size={14} />} onClick={openTransfer}>Transfer</Button>
                </div>
              ) : null}
              {canCloseWorkspace ? (
                <div className="mer-totals__row">
                  <span><strong>Close workspace</strong><br /><small>Permanently delete this workspace and every record in it.</small></span>
                  <Button variant="danger" icon={<XOctagon size={14} />} onClick={openClose}>Close workspace</Button>
                </div>
              ) : null}
            </div>
            <p className="mer-hint">
              <AlertTriangle size={12} aria-hidden="true" /> Closing the workspace cannot be reversed and immediately invalidates all credentials.
            </p>
          </div>
        ) : null}
      </Card>

      {/* ---------- Edit payout bank Sheet ---------- */}
      <Sheet
        open={!!payoutOpen}
        onClose={() => setPayoutOpen(null)}
        title="Edit payout bank"
        description="We'll send a tiny micro-deposit to verify before switching."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPayoutOpen(null)}>Cancel</Button>
            <Button onClick={submitPayoutEdit} icon={<Building2 size={14} />}>Verify & save</Button>
          </>
        }
      >
        {payoutOpen ? (
          <div className="sp-form-grid">
            <Field label="Bank">
              <SelectInput value={payoutOpen.bank} onChange={(e) => setPayoutOpen((prev) => (prev ? { ...prev, bank: e.target.value } : prev))}>
                <option>GTBank</option>
                <option>Access Bank</option>
                <option>Zenith Bank</option>
                <option>UBA</option>
                <option>Sterling Bank</option>
              </SelectInput>
            </Field>
            <Field label="Account number">
              <TextInput
                value={payoutOpen.accountNumber}
                onChange={(e) => setPayoutOpen((prev) => (prev ? { ...prev, accountNumber: e.target.value } : prev))}
                maxLength={10}
              />
            </Field>
            <Field label="Statement descriptor" hint="Up to 22 chars · appears on customer card statements.">
              <TextInput
                value={payoutOpen.descriptor}
                onChange={(e) => setPayoutOpen((prev) => (prev ? { ...prev, descriptor: e.target.value } : prev))}
                maxLength={22}
              />
            </Field>
          </div>
        ) : null}
      </Sheet>

      {/* ---------- Edit dunning template Sheet ---------- */}
      <Sheet
        open={!!editingTemplate}
        onClose={() => setEditingTemplate(null)}
        title="Edit dunning template"
        description="Use {{name}} and {{amount}} to interpolate customer details."
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingTemplate(null)}>Cancel</Button>
            <Button onClick={saveTemplate} icon={<Save size={14} />}>Save template</Button>
          </>
        }
      >
        {editingTemplate ? (
          <div className="sp-form-grid">
            <Field label="Label">
              <TextInput
                value={editingTemplate.label}
                onChange={(e) => setEditingTemplate({ ...editingTemplate, label: e.target.value })}
              />
            </Field>
            <Field label="Body">
              <textarea
                className="sp-input"
                rows={6}
                value={editingTemplate.body}
                onChange={(e) => setEditingTemplate({ ...editingTemplate, body: e.target.value })}
              />
            </Field>
          </div>
        ) : null}
      </Sheet>

      {/* ---------- Transfer ownership Modal ---------- */}
      <Modal
        open={!!transferOpen}
        onClose={() => setTransferOpen(null)}
        title="Transfer ownership"
        description="Pick a teammate to become the new Owner. You'll be downgraded to Admin."
        footer={
          <>
            <Button variant="ghost" onClick={() => setTransferOpen(null)}>Cancel</Button>
            <Button variant="danger" onClick={submitTransfer} icon={<Crown size={14} />} disabled={saving === "ownership"}>
              {saving === "ownership" ? "Transferring..." : "Transfer ownership"}
            </Button>
          </>
        }
      >
        {transferOpen ? (
          <div className="sp-form-grid">
            <Field label="New owner email">
              <SelectInput
                value={transferOpen.newOwnerEmail}
                onChange={(e) => setTransferOpen({ newOwnerEmail: e.target.value })}
              >
                <option value="">— pick a teammate —</option>
                {teamMembers
                  .filter((m) => m.role !== "Owner" && m.status === "active")
                  .map((m) => (
                    <option key={m.id} value={m.email}>{m.name} — {m.email}</option>
                  ))}
              </SelectInput>
            </Field>
            <p className="mer-hint">
              <AlertTriangle size={12} aria-hidden="true" /> Only the Owner can perform billing-critical actions (payouts, workspace closure).
            </p>
          </div>
        ) : null}
      </Modal>

      {/* ---------- Close workspace Modal ---------- */}
      <Modal
        open={!!closeOpen}
        onClose={() => setCloseOpen(null)}
        title="Close workspace permanently"
        description={`Type "${org.tradingName}" to confirm. This deletes every record in this workspace and cannot be undone.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCloseOpen(null)}>Cancel</Button>
            <Button variant="danger" onClick={submitClose} icon={<XOctagon size={14} />} disabled={saving === "close"}>
              {saving === "close" ? "Closing..." : "Close workspace"}
            </Button>
          </>
        }
      >
        {closeOpen ? (
          <div className="sp-form-grid">
            <Field label={`Type "${org.tradingName}"`}>
              <TextInput
                value={closeOpen.confirmText}
                onChange={(e) => setCloseOpen({ confirmText: e.target.value })}
                placeholder={org.tradingName}
              />
            </Field>
            <p className="mer-hint">
              <Mail size={12} aria-hidden="true" /> A confirmation email will be sent to the Owner before final deletion.
            </p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function presetFor(schedule: number[]): "gentle" | "standard" | "aggressive" {
  const joined = schedule.join(",");
  if (joined === "24,72,168") return "gentle";
  if (joined === "3,12,24,48") return "aggressive";
  return "standard";
}
