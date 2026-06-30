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
  StatCard,
  Tabs,
  TextInput,
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import {
  Copy,
  KeyRound,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Trash2
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { usePermissions } from "../auth/AuthContext";
import { loadSigningKeys, rotateSigningKeys, type SigningKeys } from "../api/signingKeys";
import { loadPublishableKeys, rotatePublishableKey, type PublishableKey } from "../api/publishableKeys";
import { useData } from "../data/store";
import { formatRelative } from "../data/selectors";
import {
  ALL_WEBHOOK_EVENTS,
  type ApiKey,
  type WebhookEndpoint,
  type WebhookEvent,
  type WebhookEventRecord
} from "../data/seed";

type TabKey = "endpoints" | "events" | "keys" | "sdk" | "signing";

interface AddEndpointForm {
  url: string;
  events: WebhookEvent[];
  signingVersion: "v1" | "v2";
}

interface ReplayState {
  endpointId: string | null;
  event: WebhookEventRecord;
}

interface DeliveriesState {
  endpoint: WebhookEndpoint;
}

interface ViewPayloadState {
  event: WebhookEventRecord;
}

interface NewKeyForm {
  name: string;
  scopes: ApiKey["scopes"];
  mode: "live" | "test";
}

interface RevealKeyState {
  name: string;
  secret: string;
}

interface RotateSigningState {
  graceHours: string;
}

export function DevelopersPage() {
  const {
    webhookEndpoints,
    webhookEvents,
    apiKeys,
    createWebhookEndpoint,
    updateWebhookEndpoint,
    removeWebhookEndpoint,
    rotateWebhookEndpointSecret,
    replayWebhookEvent,
    generateApiKey,
    revokeApiKey,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canManageWebhooks = can("manage_webhook_endpoints");
  const canReplay = can("replay_webhooks");
  const canManageKeys = can("manage_api_keys");
  const canManageSigning = can("manage_webhook_endpoints"); // signing keys are owner/dev tooling

  const [tab, setTab] = useState<TabKey>("endpoints");
  const [addOpen, setAddOpen] = useState<AddEndpointForm | null>(null);
  const [replayOpen, setReplayOpen] = useState<ReplayState | null>(null);
  const [deliveriesOpen, setDeliveriesOpen] = useState<DeliveriesState | null>(null);
  const [payloadOpen, setPayloadOpen] = useState<ViewPayloadState | null>(null);
  const [newKeyOpen, setNewKeyOpen] = useState<NewKeyForm | null>(null);
  const [revealKey, setRevealKey] = useState<RevealKeyState | null>(null);
  const [rotateSigningOpen, setRotateSigningOpen] = useState<RotateSigningState | null>(null);
  const [savingEndpoint, setSavingEndpoint] = useState(false);
  const [replaying, setReplaying] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [signingKeys, setSigningKeys] = useState<SigningKeys | null>(null);
  const [publishableKeys, setPublishableKeys] = useState<PublishableKey[] | null>(null);
  const [publishableMode, setPublishableMode] = useState<"test" | "live">("test");
  const [loadingSigning, setLoadingSigning] = useState(false);
  const [loadingPublishable, setLoadingPublishable] = useState(false);
  const [rotatingSigning, setRotatingSigning] = useState(false);
  const [rotatingPublishable, setRotatingPublishable] = useState(false);

  useEffect(() => {
    if (tab !== "signing" || signingKeys) return;
    let cancelled = false;
    setLoadingSigning(true);
    loadSigningKeys()
      .then((keys) => {
        if (!cancelled) setSigningKeys(keys);
      })
      .catch((err) => {
        if (cancelled) return;
        notify({
          tone: "danger",
          title: "Could not load signing keys",
          description: isApiError(err) ? err.reason : "Refresh the dashboard and try again."
        });
      })
      .finally(() => {
        if (!cancelled) setLoadingSigning(false);
      });
    return () => {
      cancelled = true;
    };
  }, [notify, signingKeys, tab]);

  useEffect(() => {
    if (tab !== "sdk" || publishableKeys) return;
    let cancelled = false;
    setLoadingPublishable(true);
    loadPublishableKeys()
      .then((keys) => {
        if (!cancelled) setPublishableKeys(keys);
      })
      .catch((err) => {
        if (cancelled) return;
        notify({
          tone: "danger",
          title: "Could not load publishable keys",
          description: isApiError(err) ? err.reason : "Refresh the dashboard and try again."
        });
      })
      .finally(() => {
        if (!cancelled) setLoadingPublishable(false);
      });
    return () => {
      cancelled = true;
    };
  }, [notify, publishableKeys, tab]);

  // ----- Endpoints stats -----
  const endpointStats = useMemo(() => {
    const active = webhookEndpoints.filter((e) => e.status === "active").length;
    const failing = webhookEndpoints.filter((e) => e.status === "failing").length;
    const avgSuccess = webhookEndpoints.length
      ? webhookEndpoints.reduce((s, e) => s + e.successRate, 0) / webhookEndpoints.length
      : 0;
    return { active, failing, avgSuccess };
  }, [webhookEndpoints]);

  // ----- Events pagination -----
  const eventsPager = usePagination(webhookEvents, 12, "events");

  // ----- Endpoints column defs -----
  const endpointColumns: DataTableColumn<WebhookEndpoint>[] = [
    {
      key: "url",
      header: "Endpoint",
      render: (ep) => (
        <span className="mer-entity-cell">
          <strong>{ep.url}</strong>
          <small>{ep.events.length} event{ep.events.length === 1 ? "" : "s"} · {ep.signingVersion.toUpperCase()}</small>
        </span>
      )
    },
    {
      key: "status",
      header: "Status",
      render: (ep) => <Badge tone={endpointTone(ep.status)}>{prettyStatus(ep.status)}</Badge>
    },
    {
      key: "success",
      header: "Success",
      align: "right",
      render: (ep) => `${(ep.successRate * 100).toFixed(1)}%`
    },
    {
      key: "lastDelivery",
      header: "Last delivery",
      render: (ep) => (ep.lastDeliveryAt && ep.lastDeliveryAt !== "—" ? formatRelative(ep.lastDeliveryAt) : "—")
    },
    {
      key: "actions",
      header: "",
      render: (ep) => {
        const lastEvent = webhookEvents.find((e) => e.endpointId === ep.id);
        return (
          <div className="mer-row-actions">
            {canReplay ? (
              <Button
                variant="ghost"
                icon={<Send size={14} />}
                onClick={() => lastEvent && setReplayOpen({ endpointId: ep.id, event: lastEvent })}
                disabled={!lastEvent}
              >
                Replay
              </Button>
            ) : null}
            <Button variant="ghost" icon={<RefreshCw size={14} />} onClick={() => setDeliveriesOpen({ endpoint: ep })}>
              Deliveries
            </Button>
            {canManageWebhooks ? (
              <Button variant="ghost" icon={<KeyRound size={14} />} onClick={() => handleRotateSecret(ep)}>
                Rotate secret
              </Button>
            ) : null}
            {canManageWebhooks ? (
              ep.status === "active" || ep.status === "failing" ? (
                <Button variant="ghost" icon={<Pause size={14} />} onClick={() => handleDisable(ep)}>
                  Disable
                </Button>
              ) : (
                <Button variant="ghost" icon={<Play size={14} />} onClick={() => handleEnable(ep)}>
                  Enable
                </Button>
              )
            ) : null}
            {canManageWebhooks ? (
              <Button variant="ghost" icon={<Trash2 size={14} />} onClick={() => handleRemove(ep)}>
                Remove
              </Button>
            ) : null}
          </div>
        );
      }
    }
  ];

  // ---------- Add endpoint ----------
  function openAddEndpoint() {
    setAddOpen({ url: "", events: [], signingVersion: "v2" });
  }
  function patchAdd(patch: Partial<AddEndpointForm>) {
    setAddOpen((prev) => (prev ? { ...prev, ...patch } : prev));
  }
  function toggleEvent(event: WebhookEvent) {
    setAddOpen((prev) => {
      if (!prev) return prev;
      return prev.events.includes(event)
        ? { ...prev, events: prev.events.filter((e) => e !== event) }
        : { ...prev, events: [...prev.events, event] };
    });
  }
  async function submitAdd() {
    if (!addOpen) return;
    if (!addOpen.url.trim() || addOpen.events.length === 0) {
      notify({ tone: "warning", title: "Missing details", description: "Endpoint URL and at least one event are required." });
      return;
    }
    if (!/^https:\/\//.test(addOpen.url.trim())) {
      notify({ tone: "warning", title: "HTTPS required", description: "Webhook endpoints must use https://." });
      return;
    }
    setSavingEndpoint(true);
    try {
      const result = await createWebhookEndpoint({
        url: addOpen.url.trim(),
        events: addOpen.events,
        status: "active",
        signingVersion: addOpen.signingVersion
      });
      logAuditEvent({ actor: "You", action: "Added webhook endpoint", target: addOpen.url.trim() });
      notify({
        tone: "success",
        title: "Endpoint added",
        description: result.secret ? `Secret: ${result.secret.slice(0, 16)}…` : `${addOpen.events.length} event(s) subscribed.`
      });
      setAddOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not add endpoint",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingEndpoint(false);
    }
  }

  // ---------- Rotate secret ----------
  async function handleRotateSecret(ep: WebhookEndpoint) {
    const ok = await confirm({
      destructive: true,
      title: "Rotate signing secret?",
      description: `The current secret for ${ep.url} stops working immediately. Update your server within 5 minutes or deliveries will fail.`,
      confirmLabel: "Rotate now"
    });
    if (!ok) return;
    try {
      const newSecret = await rotateWebhookEndpointSecret(ep.id);
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        navigator.clipboard.writeText(newSecret).catch(() => undefined);
      }
      logAuditEvent({ actor: "You", action: "Rotated webhook secret", target: ep.url });
      notify({
        tone: "warning",
        title: "Secret rotated",
        description: `New secret copied to clipboard: ${newSecret.slice(0, 12)}…`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not rotate secret",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  // ---------- Disable / Enable ----------
  async function handleDisable(ep: WebhookEndpoint) {
    const ok = await confirm({
      title: `Disable ${ep.url}?`,
      description: "Deliveries will stop until you re-enable. Existing events will not be retried.",
      confirmLabel: "Disable"
    });
    if (!ok) return;
    try {
      await updateWebhookEndpoint(ep.id, { status: "disabled" });
      logAuditEvent({ actor: "You", action: "Disabled webhook endpoint", target: ep.url });
      notify({ tone: "info", title: "Endpoint disabled", description: ep.url });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not disable endpoint",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }
  async function handleEnable(ep: WebhookEndpoint) {
    try {
      await updateWebhookEndpoint(ep.id, { status: "active" });
      logAuditEvent({ actor: "You", action: "Enabled webhook endpoint", target: ep.url });
      notify({ tone: "success", title: "Endpoint enabled", description: ep.url });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not enable endpoint",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  // ---------- Remove ----------
  async function handleRemove(ep: WebhookEndpoint) {
    const ok = await confirm({
      destructive: true,
      title: "Remove endpoint?",
      description: `${ep.url} will no longer receive any events. This cannot be undone.`,
      confirmLabel: "Remove endpoint"
    });
    if (!ok) return;
    try {
      await removeWebhookEndpoint(ep.id);
      logAuditEvent({ actor: "You", action: "Removed webhook endpoint", target: ep.url });
      notify({ tone: "warning", title: "Endpoint removed", description: ep.url });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not remove endpoint",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  // ---------- Events ----------
  const eventsColumns: DataTableColumn<WebhookEventRecord>[] = [
    {
      key: "event",
      header: "Event",
      render: (e) => (
        <span className="mer-entity-cell">
          <strong>{e.event}</strong>
          <small>{e.id}</small>
        </span>
      )
    },
    {
      key: "endpoint",
      header: "Endpoint",
      render: (e) => {
        const endpoint = webhookEndpoints.find((ep) => ep.id === e.endpointId);
        return endpoint ? endpoint.url : <span className="mer-muted">—</span>;
      }
    },
    {
      key: "status",
      header: "Status",
      render: (e) => <Badge tone={deliveryTone(e.status)}>{prettyStatus(e.status)}</Badge>
    },
    {
      key: "attempts",
      header: "Attempts",
      align: "right",
      render: (e) => String(e.attempts)
    },
    {
      key: "occurred",
      header: "Occurred",
      render: (e) => formatRelative(e.occurredAt)
    },
    {
      key: "actions",
      header: "",
      render: (e) => (
        <div className="mer-row-actions">
          <Button variant="ghost" onClick={() => setPayloadOpen({ event: e })}>View payload</Button>
          {canReplay ? (
            <Button
              variant="ghost"
              icon={<Send size={14} />}
              onClick={() => setReplayOpen({ endpointId: e.endpointId, event: e })}
            >
              Replay
            </Button>
          ) : null}
        </div>
      )
    }
  ];

  // ---------- Replay ----------
  async function submitReplay() {
    if (!replayOpen) return;
    const endpoint = webhookEndpoints.find((ep) => ep.id === replayOpen.endpointId);
    if (!endpoint) {
      notify({ tone: "warning", title: "Pick an endpoint", description: "Select where to replay this event." });
      return;
    }
    setReplaying(true);
    try {
      await replayWebhookEvent(replayOpen.event.id);
      logAuditEvent({ actor: "You", action: "Replayed webhook event", target: `${replayOpen.event.event} → ${endpoint.url}` });
      notify({
        tone: "success",
        title: "Event replayed",
        description: `${replayOpen.event.event} re-sent to matching enabled endpoints.`
      });
      setReplayOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not replay event",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setReplaying(false);
    }
  }

  // ---------- API keys ----------
  const keysColumns: DataTableColumn<ApiKey>[] = [
    {
      key: "name",
      header: "Name",
      render: (k) => (
        <span className="mer-entity-cell">
          <strong>{k.name}</strong>
          <small>{k.prefix}…</small>
        </span>
      )
    },
    {
      key: "scopes",
      header: "Scopes",
      render: (k) => (
        <span className="mer-pill-row">
          {k.scopes.map((s) => <Badge key={s} tone={s === "admin" ? "danger" : s === "write" ? "warning" : "info"}>{s}</Badge>)}
        </span>
      )
    },
    {
      key: "status",
      header: "Status",
      render: (k) => <Badge tone={k.status === "active" ? "success" : "neutral"}>{prettyStatus(k.status)}</Badge>
    },
    {
      key: "lastUsed",
      header: "Last used",
      render: (k) => (k.lastUsedAt && k.lastUsedAt !== "—" ? formatRelative(k.lastUsedAt) : "—")
    },
    ...(canManageKeys
      ? [
          {
            key: "actions",
            header: "",
            render: (k: ApiKey) => (
              <div className="mer-row-actions">
                <Button variant="ghost" icon={<RefreshCw size={14} />} onClick={() => handleRollKey(k)} disabled={k.status !== "active" || savingKey}>Roll</Button>
                <Button variant="ghost" icon={<Trash2 size={14} />} onClick={() => handleRevokeKey(k)} disabled={k.status !== "active" || savingKey}>Revoke</Button>
              </div>
            )
          } as DataTableColumn<ApiKey>
        ]
      : [])
  ];

  function openGenerate() {
    setNewKeyOpen({ name: "", scopes: ["read"], mode: "live" });
  }
  function patchNewKey(patch: Partial<NewKeyForm>) {
    setNewKeyOpen((prev) => (prev ? { ...prev, ...patch } : prev));
  }
  function toggleScope(scope: "read" | "write" | "admin") {
    setNewKeyOpen((prev) => {
      if (!prev) return prev;
      return prev.scopes.includes(scope)
        ? { ...prev, scopes: prev.scopes.filter((s) => s !== scope) }
        : { ...prev, scopes: [...prev.scopes, scope] };
    });
  }
  async function submitGenerate() {
    if (!newKeyOpen) return;
    if (!newKeyOpen.name.trim() || newKeyOpen.scopes.length === 0) {
      notify({ tone: "warning", title: "Missing details", description: "Name and at least one scope are required." });
      return;
    }
    setSavingKey(true);
    try {
      const result = await generateApiKey({
        name: newKeyOpen.name.trim(),
        scopes: newKeyOpen.scopes,
        mode: newKeyOpen.mode
      });
      logAuditEvent({ actor: "You", action: "Generated API key", target: newKeyOpen.name.trim() });
      setRevealKey({ name: newKeyOpen.name.trim(), secret: result.secret });
      setNewKeyOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not generate key",
        description: isApiError(err) ? err.reason : "The backend rejected the API key request."
      });
    } finally {
      setSavingKey(false);
    }
  }

  function copyRevealedKey() {
    if (!revealKey) return;
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(revealKey.secret).catch(() => undefined);
    }
    notify({ tone: "info", title: "Copied", description: "Key copied to clipboard. Store it securely." });
  }

  async function handleRollKey(key: ApiKey) {
    const ok = await confirm({
      destructive: true,
      title: `Roll ${key.name}?`,
      description: "The current secret stops working immediately. Update your server with the new secret right away.",
      confirmLabel: "Roll key"
    });
    if (!ok) return;
    setSavingKey(true);
    try {
      await revokeApiKey(key.id);
      const mode = key.prefix.includes("_live_") ? "live" : "test";
      const result = await generateApiKey({
        name: key.name,
        scopes: key.scopes,
        mode
      });
      logAuditEvent({ actor: "You", action: "Rolled API key", target: key.name });
      setRevealKey({ name: `${key.name} (rolled)`, secret: result.secret });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not roll key",
        description: isApiError(err) ? err.reason : "The backend rejected the key rotation."
      });
    } finally {
      setSavingKey(false);
    }
  }

  async function handleRevokeKey(key: ApiKey) {
    const ok = await confirm({
      destructive: true,
      title: `Revoke ${key.name}?`,
      description: "This key will stop working immediately. Anything using it will get 401 errors.",
      confirmLabel: "Revoke"
    });
    if (!ok) return;
    setSavingKey(true);
    try {
      await revokeApiKey(key.id);
      logAuditEvent({ actor: "You", action: "Revoked API key", target: key.name });
      notify({ tone: "warning", title: "Key revoked", description: key.name });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not revoke key",
        description: isApiError(err) ? err.reason : "The backend rejected the revoke request."
      });
    } finally {
      setSavingKey(false);
    }
  }

  // ---------- Signing ----------
  function copySigning(value: string, label: string) {
    if (!value) {
      notify({ tone: "warning", title: "No key available", description: "Load or rotate signing keys first." });
      return;
    }
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(value).catch(() => undefined);
    }
    logAuditEvent({ actor: "You", action: "Copied signing key", target: label });
    notify({ tone: "info", title: `${label} copied`, description: "Stored to clipboard." });
  }
  function openRotateSigning() {
    setRotateSigningOpen({ graceHours: "24" });
  }
  async function submitRotateSigning() {
    if (!rotateSigningOpen) return;
    const grace = Number(rotateSigningOpen.graceHours);
    if (!Number.isFinite(grace) || grace < 0 || grace > 168) {
      notify({ tone: "warning", title: "Invalid grace period", description: "Grace must be between 0 and 168 hours." });
      return;
    }
    const ok = await confirm({
      destructive: true,
      title: "Rotate signing keys?",
      description: `The current key keeps working for ${grace}h while you migrate. After that, only the new key validates.`,
      confirmLabel: "Rotate keys"
    });
    if (!ok) return;
    setRotatingSigning(true);
    try {
      const keys = await rotateSigningKeys(grace);
      setSigningKeys(keys);
      logAuditEvent({ actor: "You", action: "Rotated signing keys", target: `${grace}h grace` });
      notify({
        tone: "warning",
        title: "Signing keys rotated",
        description: `New primary key active. Old key works for ${grace}h.`
      });
      setRotateSigningOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not rotate signing keys",
        description: isApiError(err) ? err.reason : "The backend rejected the rotation request."
      });
    } finally {
      setRotatingSigning(false);
    }
  }

  const activePublishableKey = publishableKeys?.find((key) => key.mode === publishableMode)?.publishableKey ?? "";
  const sdkInstallSnippet = "npm install @subpilot/portal-js";
  const sdkReactSnippet = `import { useState } from "react";
import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingPortal({ portalToken }) {
  const [open, setOpen] = useState(true);

  return (
    <SubPilotPortal
      publishableKey="${activePublishableKey || `pk_${publishableMode}_...`}"
      token={portalToken}
      apiBaseUrl="https://api.subpilot.dev/api/v1"
      displayMode="modal"
      open={open}
      showCloseButton
      closeLabel="Done"
      onClose={() => setOpen(false)}
    />
  );
}`;
  const sdkServerSnippet = `// Server-side only: create the short-lived portal token with your secret API key.
const session = await fetch("https://api.subpilot.dev/api/v1/customers/{customer_id}/portal-sessions/", {
  method: "POST",
  headers: {
    "Authorization": "Bearer nse_${publishableMode}_...",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ send_email: false })
}).then((res) => res.json());

return { portalToken: session.token };`;

  function copyText(value: string, label: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(value).catch(() => undefined);
    }
    notify({ tone: "info", title: `${label} copied`, description: "Stored to clipboard." });
  }

  async function handleRotatePublishable() {
    const ok = await confirm({
      destructive: true,
      title: `Rotate ${publishableMode} publishable key?`,
      description: "Frontend apps using the old key must be redeployed with the new value.",
      confirmLabel: "Rotate key"
    });
    if (!ok) return;
    setRotatingPublishable(true);
    try {
      const rotated = await rotatePublishableKey(publishableMode);
      setPublishableKeys((prev) => {
        const keys = prev ?? [];
        const found = keys.some((key) => key.mode === rotated.mode);
        return found ? keys.map((key) => (key.mode === rotated.mode ? rotated : key)) : [...keys, rotated];
      });
      logAuditEvent({ actor: "You", action: "Rotated publishable key", target: publishableMode });
      notify({ tone: "warning", title: "Publishable key rotated", description: `${publishableMode} frontend key updated.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not rotate publishable key",
        description: isApiError(err) ? err.reason : "The backend rejected the rotation request."
      });
    } finally {
      setRotatingPublishable(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Integrations"
        title="Developers"
        description="Webhooks, events, API keys, and signing rotation. The plumbing your servers depend on."
        actions={
          tab === "endpoints" && canManageWebhooks ? (
            <Button icon={<Plus size={16} />} onClick={openAddEndpoint}>Add endpoint</Button>
          ) : tab === "keys" && canManageKeys ? (
            <Button icon={<Plus size={16} />} onClick={openGenerate}>Generate key</Button>
          ) : tab === "sdk" && canManageKeys ? (
            <Button icon={<RefreshCw size={16} />} onClick={() => void handleRotatePublishable()} variant="secondary" disabled={rotatingPublishable}>
              {rotatingPublishable ? "Rotating..." : "Rotate publishable key"}
            </Button>
          ) : tab === "signing" && canManageSigning ? (
            <Button icon={<RefreshCw size={16} />} onClick={openRotateSigning} variant="secondary">Rotate signing</Button>
          ) : undefined
        }
      />

      <section className="sp-grid sp-grid-4">
        <StatCard label="Active endpoints" value={String(endpointStats.active)} delta={`${webhookEndpoints.length} total`} tone="info" />
        <StatCard label="Failing endpoints" value={String(endpointStats.failing)} delta={endpointStats.failing > 0 ? "Investigate" : "All healthy"} tone={endpointStats.failing > 0 ? "danger" : "success"} />
        <StatCard label="Avg success" value={`${(endpointStats.avgSuccess * 100).toFixed(1)}%`} delta="Across endpoints" tone="neutral" />
        <StatCard label="Active API keys" value={String(apiKeys.filter((k) => k.status === "active").length)} delta={`${apiKeys.length} total`} tone="info" />
      </section>

      <Card>
        <Tabs
          value={tab}
          onChange={(v) => setTab(v as TabKey)}
          items={[
            { label: "Endpoints", value: "endpoints", count: webhookEndpoints.length },
            { label: "Events", value: "events", count: webhookEvents.length },
            { label: "API keys", value: "keys", count: apiKeys.length },
            { label: "SDK", value: "sdk" },
            { label: "Signing", value: "signing" }
          ]}
        />

        {tab === "endpoints" ? (
          <>
            <CardHeader title="Webhook endpoints" description="Each subscriber receives signed POSTs for the events you select." />
            <DataTable
              columns={endpointColumns}
              rows={webhookEndpoints}
              getRowKey={(ep) => ep.id}
              emptyText="No endpoints yet — add one to start receiving events."
            />
          </>
        ) : null}

        {tab === "events" ? (
          <>
            <CardHeader title="Event log" description="Every webhook delivery, succeeded or failed, with a payload preview." />
            <DataTable
              columns={eventsColumns}
              rows={eventsPager.slice}
              getRowKey={(e) => e.id}
              emptyText="No events yet."
            />
            <Pagination page={eventsPager.page} pageCount={eventsPager.pageCount} onPageChange={eventsPager.setPage} totalLabel={eventsPager.totalLabel} />
          </>
        ) : null}

        {tab === "keys" ? (
          <>
            <CardHeader title="API keys" description="Server-side keys for the SubPilot REST API. Treat them like passwords." />
            <DataTable
              columns={keysColumns}
              rows={apiKeys}
              getRowKey={(k) => k.id}
              emptyText="No API keys generated."
            />
          </>
        ) : null}

        {tab === "sdk" ? (
          <div className="mer-section">
            <CardHeader title="Frontend SDK" description="Install the customer portal package in your app and initialize it with a publishable key." />
            <div className="sp-form-grid">
              <Field label="Mode">
                <SegmentedControl
                  value={publishableMode}
                  onChange={(v) => setPublishableMode(v as "test" | "live")}
                  label="Publishable key mode"
                  items={[
                    { label: "Test mode", value: "test" },
                    { label: "Live mode", value: "live" }
                  ]}
                />
              </Field>
              <div className="mer-totals">
                <div className="mer-totals__row">
                  <span>{publishableMode === "live" ? "Live" : "Test"} publishable key</span>
                  <span className="mer-key-row">
                    <code>{loadingPublishable ? "Loading..." : activePublishableKey || "No publishable key loaded"}</code>
                    <Button
                      variant="ghost"
                      icon={<Copy size={14} />}
                      onClick={() => copyText(activePublishableKey, "Publishable key")}
                      disabled={!activePublishableKey}
                    >
                      Copy
                    </Button>
                  </span>
                </div>
              </div>
              <Field label="Install">
                <div className="mer-pre">{sdkInstallSnippet}</div>
              </Field>
              <Field label="React embed">
                <div className="mer-pre">{sdkReactSnippet}</div>
              </Field>
              <Field label="Create portal token">
                <div className="mer-pre">{sdkServerSnippet}</div>
              </Field>
              <p className="mer-hint">
                <ShieldCheck size={12} aria-hidden="true" /> Use publishable keys in browser code. Create portal tokens on your server with a secret API key.
              </p>
            </div>
          </div>
        ) : null}

        {tab === "signing" ? (
          <div className="mer-section">
            <CardHeader title="Webhook signing keys" description="Verify the X-SubPilot-Signature header server-side using these secrets." />
            <div className="mer-totals">
              <div className="mer-totals__row">
                <span>Primary (active{signingKeys ? ` · ${signingKeys.mode}` : ""})</span>
                <span className="mer-key-row">
                  <code>{loadingSigning ? "Loading..." : signingKeys?.primaryMasked || "No key loaded"}</code>
                  <Button variant="ghost" icon={<Copy size={14} />} onClick={() => copySigning(signingKeys?.primary ?? "", "Primary signing key")} disabled={!signingKeys?.primary}>Copy</Button>
                </span>
              </div>
              <div className="mer-totals__row">
                <span>Previous (in rotation)</span>
                <span className="mer-key-row">
                  <code>{loadingSigning ? "Loading..." : signingKeys?.previousMasked || "No previous key"}</code>
                  <Button variant="ghost" icon={<Copy size={14} />} onClick={() => copySigning(signingKeys?.previous ?? "", "Previous signing key")} disabled={!signingKeys?.previous}>Copy</Button>
                </span>
              </div>
              <div className="mer-totals__row">
                <span>Previous expires</span>
                <strong>{signingKeys?.previousExpiresAt ? new Date(signingKeys.previousExpiresAt).toLocaleString() : "—"}</strong>
              </div>
            </div>
            <p className="mer-hint">
              <ShieldCheck size={12} aria-hidden="true" /> During rotation, both keys validate signatures so your migration is zero-downtime.
            </p>
          </div>
        ) : null}
      </Card>

      {/* ---------- Add endpoint Sheet ---------- */}
      <Sheet
        open={!!addOpen}
        onClose={() => setAddOpen(null)}
        title="Add webhook endpoint"
        description="Subscribe a URL to selected events. Only HTTPS endpoints are accepted."
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddOpen(null)}>Cancel</Button>
            <Button onClick={submitAdd} icon={<Plus size={14} />} disabled={savingEndpoint}>
              {savingEndpoint ? "Adding…" : "Add endpoint"}
            </Button>
          </>
        }
      >
        {addOpen ? (
          <div className="sp-form-grid">
            <Field label="URL" hint="Must start with https://">
              <TextInput
                placeholder="https://api.example.com/webhooks/subpilot"
                value={addOpen.url}
                onChange={(e) => patchAdd({ url: e.target.value })}
              />
            </Field>
            <Field label="Signing version">
              <SegmentedControl
                value={addOpen.signingVersion}
                onChange={(v) => patchAdd({ signingVersion: v as "v1" | "v2" })}
                label="Signing version"
                items={[
                  { label: "v1 (legacy)", value: "v1" },
                  { label: "v2 (recommended)", value: "v2" }
                ]}
              />
            </Field>
            <Field label={`Events (${addOpen.events.length} selected)`}>
              <div className="mer-checkbox-grid">
                {ALL_WEBHOOK_EVENTS.map((event) => (
                  <Checkbox
                    key={event}
                    label={event}
                    checked={addOpen.events.includes(event)}
                    onChange={() => toggleEvent(event)}
                  />
                ))}
              </div>
            </Field>
          </div>
        ) : null}
      </Sheet>

      {/* ---------- Replay Modal ---------- */}
      <Modal
        open={!!replayOpen}
        onClose={() => setReplayOpen(null)}
        title="Replay event"
        description={replayOpen ? `Re-deliver ${replayOpen.event.event} (${replayOpen.event.id}).` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={() => setReplayOpen(null)}>Cancel</Button>
            <Button onClick={submitReplay} icon={<Send size={14} />} disabled={replaying}>
              {replaying ? "Replaying…" : "Replay"}
            </Button>
          </>
        }
      >
        {replayOpen ? (
          <div className="sp-form-grid">
            <Field label="Endpoint">
              <SelectInput
                value={replayOpen.endpointId ?? ""}
                onChange={(e) => setReplayOpen((prev) => (prev ? { ...prev, endpointId: e.target.value || null } : prev))}
              >
                <option value="">— pick an endpoint —</option>
                {webhookEndpoints.map((ep) => (
                  <option key={ep.id} value={ep.id}>{ep.url}</option>
                ))}
              </SelectInput>
            </Field>
            <div className="mer-pre">{replayOpen.event.payloadPreview}</div>
          </div>
        ) : null}
      </Modal>

      {/* ---------- Deliveries Sheet ---------- */}
      <Sheet
        open={!!deliveriesOpen}
        onClose={() => setDeliveriesOpen(null)}
        title="Recent deliveries"
        description={deliveriesOpen ? deliveriesOpen.endpoint.url : ""}
        footer={<Button variant="ghost" onClick={() => setDeliveriesOpen(null)}>Close</Button>}
      >
        {deliveriesOpen ? (
          <div className="sp-form-grid">
            <ul className="mer-portal-history">
              {webhookEvents
                .filter((e) => e.endpointId === deliveriesOpen.endpoint.id)
                .slice(0, 10)
                .map((e) => (
                  <li key={e.id}>
                    <div>
                      <strong>{e.event}</strong>
                      <small>{formatRelative(e.occurredAt)} · {e.attempts} attempt{e.attempts === 1 ? "" : "s"}</small>
                    </div>
                    <Badge tone={deliveryTone(e.status)}>{prettyStatus(e.status)}</Badge>
                    <Button variant="ghost" onClick={() => setPayloadOpen({ event: e })}>Payload</Button>
                  </li>
                ))}
            </ul>
          </div>
        ) : null}
      </Sheet>

      {/* ---------- View payload Sheet ---------- */}
      <Sheet
        open={!!payloadOpen}
        onClose={() => setPayloadOpen(null)}
        title="Event payload"
        description={payloadOpen ? `${payloadOpen.event.event} · ${payloadOpen.event.id}` : ""}
        footer={<Button variant="ghost" onClick={() => setPayloadOpen(null)}>Close</Button>}
      >
        {payloadOpen ? (
          <div className="mer-pre">
{`{
  "id": "${payloadOpen.event.id}",
  "type": "${payloadOpen.event.event}",
  "occurred_at": "${payloadOpen.event.occurredAt}",
  "attempts": ${payloadOpen.event.attempts},
  "data": {
    "object": "preview",
    "summary": "${payloadOpen.event.payloadPreview.replace(/"/g, '\\"')}"
  }
}`}
          </div>
        ) : null}
      </Sheet>

      {/* ---------- Generate API key Modal ---------- */}
      <Modal
        open={!!newKeyOpen}
        onClose={() => setNewKeyOpen(null)}
        title="Generate API key"
        description="Pick the scopes carefully. The full secret is shown only once after creation."
        footer={
          <>
            <Button variant="ghost" onClick={() => setNewKeyOpen(null)}>Cancel</Button>
            <Button onClick={submitGenerate} icon={<KeyRound size={14} />} disabled={savingKey}>
              {savingKey ? "Generating…" : "Generate"}
            </Button>
          </>
        }
      >
        {newKeyOpen ? (
          <div className="sp-form-grid">
            <Field label="Name" hint="e.g. Production server, Local development.">
              <TextInput
                placeholder="Production server"
                value={newKeyOpen.name}
                onChange={(e) => patchNewKey({ name: e.target.value })}
              />
            </Field>
            <Field label="Mode">
              <SegmentedControl
                value={newKeyOpen.mode}
                onChange={(v) => patchNewKey({ mode: v as "live" | "test" })}
                label="Mode"
                items={[
                  { label: "Test mode", value: "test" },
                  { label: "Live mode", value: "live" }
                ]}
              />
            </Field>
            <Field label="Scopes">
              <div className="mer-checkbox-grid">
                <Checkbox label="read" description="Fetch all resources." checked={newKeyOpen.scopes.includes("read")} onChange={() => toggleScope("read")} />
                <Checkbox label="write" description="Create and modify resources." checked={newKeyOpen.scopes.includes("write")} onChange={() => toggleScope("write")} />
                <Checkbox label="admin" description="Includes destructive actions." checked={newKeyOpen.scopes.includes("admin")} onChange={() => toggleScope("admin")} />
              </div>
            </Field>
          </div>
        ) : null}
      </Modal>

      {/* ---------- Reveal key Modal (one-time) ---------- */}
      <Modal
        open={!!revealKey}
        onClose={() => setRevealKey(null)}
        title="Copy your new key"
        description="This is the only time the full secret will be shown. Store it in your secrets manager now."
        footer={
          <>
            <Button onClick={() => setRevealKey(null)}>I've stored it safely</Button>
          </>
        }
      >
        {revealKey ? (
          <div className="sp-form-grid">
            <div className="mer-totals">
              <div className="mer-totals__row"><span>Name</span><strong>{revealKey.name}</strong></div>
            </div>
            <div className="mer-pre">{revealKey.secret}</div>
            <Button variant="secondary" icon={<Copy size={14} />} onClick={copyRevealedKey}>Copy to clipboard</Button>
          </div>
        ) : null}
      </Modal>

      {/* ---------- Rotate signing keys Modal ---------- */}
      <Modal
        open={!!rotateSigningOpen}
        onClose={() => setRotateSigningOpen(null)}
        title="Rotate signing keys"
        description="Generates a new primary key. Old key keeps working during the grace window."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRotateSigningOpen(null)}>Cancel</Button>
            <Button onClick={submitRotateSigning} icon={<RefreshCw size={14} />} disabled={rotatingSigning}>
              {rotatingSigning ? "Rotating..." : "Rotate"}
            </Button>
          </>
        }
      >
        {rotateSigningOpen ? (
          <div className="sp-form-grid">
            <Field label="Grace period (hours)" hint="0–168. Both keys validate signatures during this window.">
              <TextInput
                type="number"
                min={0}
                max={168}
                value={rotateSigningOpen.graceHours}
                onChange={(e) => setRotateSigningOpen({ graceHours: e.target.value })}
              />
            </Field>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function endpointTone(status: WebhookEndpoint["status"]): BadgeTone {
  switch (status) {
    case "active": return "success";
    case "failing": return "danger";
    case "disabled": return "neutral";
    default: return "neutral";
  }
}

function deliveryTone(status: WebhookEventRecord["status"]): BadgeTone {
  switch (status) {
    case "delivered": return "success";
    case "failed": return "danger";
    case "pending": return "warning";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
