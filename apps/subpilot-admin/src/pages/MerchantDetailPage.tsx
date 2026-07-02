import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  Pagination,
  SegmentedControl,
  SelectInput,
  Sheet,
  StatCard,
  Tabs,
  TextInput
} from "@subpilot/ui";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileText,
  Key,
  Mail,
  MapPin,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Trash2,
  UserPlus,
  Webhook
} from "lucide-react";
import { useMerchantDetail, type MerchantDetailKyc } from "../api/merchantDetail";
import {
  useMerchantAudit,
  useMerchantPayments,
  useMerchantSubscriptions,
  useMerchantWebhooks
} from "../api/merchantTabs";
import { useMerchantConfig } from "../api/merchantConfig";
import type { PaymentRow } from "../api/payments";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { usePlatformPermissions } from "../auth/AuthContext";

type TabKey = "overview" | "kyc" | "subscriptions" | "payments" | "webhooks" | "config" | "audit";

const PAGE_SIZE = 10;

export function MerchantDetailPage() {
  const { merchantId } = useParams<{ merchantId: string }>();
  const {
    detail,
    loading,
    notFound,
    error,
    suspend,
    reactivate,
    addNote,
    rotateWebhookSecret,
    forceClose,
    impersonate,
    refundPayment,
    retryWebhook,
    runKycReview,
  } = useMerchantDetail(merchantId);
  const [tab, setTab] = useState<TabKey>("overview");
  const { notify, confirm } = useFeedback();
  const {
    canEditMerchantConfig,
    canRotateMerchantSecret,
    canForceCloseSubscription,
    canOperate,
    canSupportAct
  } = usePlatformPermissions();

  // Per-tab pagination state (server-side).
  const [subsPage, setSubsPage] = useState(1);
  const [paymentsPage, setPaymentsPage] = useState(1);
  const [webhooksPage, setWebhooksPage] = useState(1);
  const [auditPage, setAuditPage] = useState(1);

  // Per-tab live data hooks.
  const subsHook = useMerchantSubscriptions(merchantId, { page: subsPage, pageSize: PAGE_SIZE });
  const paymentsHook = useMerchantPayments(merchantId, { page: paymentsPage, pageSize: PAGE_SIZE });
  const webhooksHook = useMerchantWebhooks(merchantId, { page: webhooksPage, pageSize: PAGE_SIZE });
  const auditHook = useMerchantAudit(merchantId, { page: auditPage, pageSize: PAGE_SIZE });
  const cfgHook = useMerchantConfig(merchantId);

  // Modal/sheet state
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [reinstateOpen, setReinstateOpen] = useState(false);
  const [kycOpen, setKycOpen] = useState(false);
  const [secretOpen, setSecretOpen] = useState(false);
  const [refundOpen, setRefundOpen] = useState<PaymentRow | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  // Form state for sheets/modals
  const [noteVisibility, setNoteVisibility] = useState("ops");
  const [noteBody, setNoteBody] = useState("");
  const [suspendReason, setSuspendReason] = useState("risk");
  const [suspendNote, setSuspendNote] = useState("");
  const [reinstateNote, setReinstateNote] = useState("");

  // KYC re-run modal
  const [kycLevel, setKycLevel] = useState<string>("Tier 2");
  const [kycReviewer, setKycReviewer] = useState<string>("Ada Okafor");
  const [kycSubmitting, setKycSubmitting] = useState(false);

  // Webhook secret rotation modal
  const [secretGrace, setSecretGrace] = useState<string>("24h");
  const [secretSubmitting, setSecretSubmitting] = useState(false);

  // Refund modal
  const [refundAmount, setRefundAmount] = useState<string>("");
  const [refundReason, setRefundReason] = useState<string>("duplicate");
  const [refundNote, setRefundNote] = useState<string>("");
  const [refundSubmitting, setRefundSubmitting] = useState(false);

  // Replay webhook in-flight state (per-row)
  const [replayingId, setReplayingId] = useState<string | null>(null);

  // Force-close in-flight
  const [closing, setClosing] = useState(false);

  // Impersonation in-flight
  const [impersonating, setImpersonating] = useState(false);

  // Config edit-sheet form state — initialized from current bundle.
  const [editCadence, setEditCadence] = useState<string>("daily");
  const [editChannels, setEditChannels] = useState<string>("email+slack");
  const [editAttempts, setEditAttempts] = useState<string>("4");
  const [editCooldown, setEditCooldown] = useState<string>("6");
  const [editBackoff, setEditBackoff] = useState<string>("exponential");
  const [editRisk, setEditRisk] = useState<string>("no");
  const [editVolMinor, setEditVolMinor] = useState<string>("0");
  const [editTicketMinor, setEditTicketMinor] = useState<string>("0");

  // Sync refund form when a payment is selected.
  useEffect(() => {
    if (refundOpen) {
      setRefundAmount(refundOpen.amount ?? "");
      setRefundReason("duplicate");
      setRefundNote("");
    }
  }, [refundOpen]);

  // Sync KYC level when modal opens.
  useEffect(() => {
    if (kycOpen) {
      setKycLevel(detail?.kyc?.level ?? "Tier 2");
      setKycReviewer(detail?.kyc?.reviewer ?? "Ada Okafor");
    }
  }, [kycOpen, detail?.kyc?.level, detail?.kyc?.reviewer]);

  // Sync edit form when sheet opens or config changes.
  useEffect(() => {
    const c = cfgHook.config;
    if (!c) return;
    setEditCadence(payoutToToken(c.limits.payoutCadence));
    setEditChannels(channelsToToken(c.limits.notificationChannels));
    setEditAttempts(String(c.retryPolicy.attempts));
    setEditCooldown(String(c.retryPolicy.cooldownHours));
    setEditBackoff(backoffToToken(c.retryPolicy.backoff));
    setEditRisk(c.limits.highRiskMcc ? "yes" : "no");
    setEditVolMinor(String(c.limits.monthlyVolumeCapMinor));
    setEditTicketMinor(String(c.limits.maxTicketMinor));
  }, [cfgHook.config, configOpen]);

  if (loading) {
    return <div className="adm-empty-state"><h2>Loading merchant…</h2></div>;
  }
  if (notFound || !detail) {
    return (
      <div className="adm-empty-state">
        <h2>Merchant not found</h2>
        <p>We couldn&rsquo;t find a merchant with id <code>{merchantId}</code>.</p>
        {error ? <p className="adm-muted">{error}</p> : null}
        <Link to="/merchants" className="adm-card-link">
          <ArrowLeft size={14} aria-hidden="true" /> Back to merchants
        </Link>
      </div>
    );
  }

  const merchant = detail;
  const kyc = detail.kyc;
  const stats = subsHook.stats;
  const planMix = subsHook.planMix;
  const cfg = cfgHook.config;

  const overviewRecentPayments = paymentsHook.rows.slice(0, 5);
  const overviewRecentDeliveries = webhooksHook.rows.slice(0, 5);

  function openKycDocument(document: MerchantDetailKyc["documents"][number]) {
    const href = document.url || document.dataUrl;
    if (!href) {
      notify({
        tone: "info",
        title: `No preview for ${document.kind}`,
        description: document.fileName
          ? `${document.fileName} was recorded, but no preview file is stored.`
          : `Document metadata exists for ${merchant.name}, but no preview file is stored.`
      });
      return;
    }
    window.open(href, "_blank", "noopener,noreferrer");
  }

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="adm-breadcrumb-eyebrow">
            <Link to="/merchants" className="adm-card-link">
              <ArrowLeft size={12} aria-hidden="true" /> Merchants
            </Link>
            <span> / {merchant.id}</span>
          </span>
        }
        title={merchant.name}
        description={`Plan: ${merchant.plan} · Owner: ${merchant.owner} · Onboarded ${merchant.createdAt}`}
        actions={
          <>
            {canSupportAct ? (
              <Button variant="ghost" icon={<MessageSquare size={16} />} onClick={() => setNoteOpen(true)}>Add note</Button>
            ) : null}
            {canSupportAct ? (
              <Button
                variant="ghost"
                icon={<ExternalLink size={16} />}
                disabled={impersonating}
                onClick={async () => {
                if (impersonating) return;
                setImpersonating(true);
                try {
                  const result = await impersonate();
                  const opened = window.open(result.redirectUrl, "_blank", "noopener,noreferrer");
                  if (!opened) {
                    notify({
                      tone: "warning",
                      title: "Pop-up blocked",
                      description: `Allow pop-ups for this site, then try again. Link is valid for ${Math.round(result.expiresIn / 60)} minutes.`,
                    });
                  } else {
                    notify({
                      tone: "success",
                      title: "Opened merchant view",
                      description: `Signed in as ${result.userName || result.userEmail} in a new tab.`,
                    });
                  }
                } catch (err) {
                  notify({
                    tone: "danger",
                    title: "Could not open merchant view",
                    description: err instanceof Error ? err.message : "Please try again.",
                  });
                } finally {
                  setImpersonating(false);
                }
              }}
            >
              Open as merchant
              </Button>
            ) : null}
            {canOperate ? (
              merchant.status === "Suspended" ? (
                <Button icon={<Play size={16} />} onClick={() => setReinstateOpen(true)}>Reinstate</Button>
              ) : (
                <Button variant="danger" icon={<Pause size={16} />} onClick={() => setSuspendOpen(true)}>Suspend</Button>
              )
            ) : null}
          </>
        }
      />

      <div className="adm-detail-meta">
        <span><Mail size={14} aria-hidden="true" /> {merchant.ownerEmail}</span>
        <span><MapPin size={14} aria-hidden="true" /> {merchant.region}</span>
        <Badge tone={merchant.environment === "Live" ? "teal" : "neutral"}>{merchant.environment}</Badge>
        <Badge tone={merchant.status === "Healthy" ? "success" : merchant.status === "At risk" ? "warning" : "danger"}>{merchant.status}</Badge>
        <Badge tone={kyc?.status === "Verified" ? "success" : kyc?.status === "Action needed" ? "warning" : kyc?.status === "Rejected" ? "danger" : "info"}>
          KYC: {kyc?.status ?? "Not submitted"}
        </Badge>
      </div>

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Overview", value: "overview" },
          { label: "KYC", value: "kyc" },
          { label: "Subscriptions", value: "subscriptions", count: stats?.active ?? subsHook.total },
          { label: "Payments", value: "payments", count: paymentsHook.total },
          { label: "Webhooks", value: "webhooks", count: webhooksHook.total },
          { label: "Config", value: "config" },
          { label: "Audit", value: "audit", count: auditHook.total }
        ]}
      />

      {tab === "overview" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="MRR" value={merchant.mrr} delta="Recurring" tone="success" />
            <StatCard label="Monthly volume" value={merchant.monthlyVolume} delta="Captured" tone="info" />
            <StatCard label="Active subs" value={String(merchant.activeSubscriptions)} delta="Live" tone="teal" />
            <StatCard
              label="Recovery rate"
              value={merchant.recoveryRate}
              delta={`${merchant.failedInvoices} failed`}
              tone={merchant.status === "Suspended" ? "danger" : merchant.status === "At risk" ? "warning" : "success"}
            />
          </section>

          <section className="sp-panel-layout">
            <Card>
              <CardHeader title="Recent payments" description="Most recent charge attempts for this merchant." />
              {overviewRecentPayments.length ? (
                <table className="sp-table">
                  <thead>
                    <tr><th>Payment</th><th>Customer</th><th>Amount</th><th>Status</th><th>Method</th><th>When</th></tr>
                  </thead>
                  <tbody>
                    {overviewRecentPayments.map((p) => (
                      <tr key={p.id}>
                        <td><code className="adm-code">{p.id}</code></td>
                        <td>{p.customer}</td>
                        <td>{p.amount}</td>
                        <td>{paymentBadge(p.status)}</td>
                        <td>{p.method}</td>
                        <td>{formatTime(p.occurredAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="adm-empty">{paymentsHook.loading ? "Loading…" : "No payment activity yet."}</p>
              )}
            </Card>

            <div className="sp-grid">
              <Card tone="mint">
                <CardHeader title="Quick actions" description="Most-used merchant operations." />
                <div className="adm-actions-grid">
                  {canOperate ? (
                    <button type="button" className="adm-action-tile" onClick={() => setKycOpen(true)}>
                      <ShieldAlert size={16} /><span>Trigger KYC review</span>
                    </button>
                  ) : null}
                  {canRotateMerchantSecret ? (
                    <button type="button" className="adm-action-tile" onClick={() => setSecretOpen(true)}>
                      <Key size={16} /><span>Rotate webhook secret</span>
                    </button>
                  ) : null}
                  {canEditMerchantConfig ? (
                    <button type="button" className="adm-action-tile" onClick={() => setConfigOpen(true)}>
                      <Sliders size={16} /><span>Edit limits & features</span>
                    </button>
                  ) : null}
                  {canSupportAct ? (
                    <button type="button" className="adm-action-tile" onClick={() => setNoteOpen(true)}>
                      <MessageSquare size={16} /><span>Leave internal note</span>
                    </button>
                  ) : null}
                </div>
              </Card>

              <Card>
                <CardHeader title="Recent webhooks" description="Outbound deliveries to this merchant&rsquo;s endpoints." />
                {overviewRecentDeliveries.length ? (
                  <ul className="adm-event-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                    {overviewRecentDeliveries.map((w) => (
                      <li key={w.id} className="adm-event-row">
                        <div>
                          <strong><code className="adm-code">{w.event}</code></strong>
                          <small>{w.attempts} attempt{w.attempts === 1 ? "" : "s"} · HTTP {w.responseCode}</small>
                        </div>
                        <Badge tone={w.status === "Delivered" ? "success" : w.status === "Retrying" ? "warning" : "danger"}>{w.status}</Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="adm-empty">{webhooksHook.loading ? "Loading…" : "No webhook deliveries yet."}</p>
                )}
              </Card>
            </div>
          </section>
        </>
      ) : null}

      {tab === "kyc" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader
              title="KYC documents"
              description={`Tier: ${kyc?.level ?? "—"} · Submitted ${kyc?.submittedAt ?? "—"}${kyc?.reviewedAt ? ` · Reviewed ${kyc.reviewedAt} by ${kyc.reviewer}` : ""}`}
              action={<Button variant="ghost" icon={<RefreshCw size={14} />} onClick={() => setKycOpen(true)}>Re-run review</Button>}
            />
            {kyc && kyc.documents.length ? (
              <ul className="adm-doc-list">
                {kyc.documents.map((d) => (
                  <li key={`${d.kind}-${d.fileName ?? d.uploadedAt}`} className="adm-doc-row">
                    <FileText size={16} aria-hidden="true" />
                    <div>
                      <strong>{d.kind}</strong>
                      <small>{d.fileName ? `${d.fileName} · ` : ""}Uploaded {d.uploadedAt}</small>
                    </div>
                    <Badge tone={d.status === "Approved" ? "success" : d.status === "Pending" ? "warning" : "danger"}>{d.status}</Badge>
                    <Button
                      variant="ghost"
                      onClick={() => openKycDocument(d)}
                    >
                      View
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="adm-empty">No KYC submission on file.</p>
            )}
          </Card>

          <Card tone={kyc?.flags?.length ? "mint" : "surface"}>
            <CardHeader title="Compliance flags" description="Risk signals and reviewer notes." />
            {kyc?.flags?.length ? (
              <ul className="adm-flag-list">
                {kyc.flags.map((f) => (
                  <li key={f}><AlertTriangle size={14} aria-hidden="true" /> {f}</li>
                ))}
              </ul>
            ) : (
              <p className="adm-empty"><CheckCircle2 size={14} /> No active flags.</p>
            )}
            <p className="adm-note">{kyc?.notes ?? "No notes yet."}</p>
            <div className="adm-form-actions">
              <Button variant="ghost" onClick={() => setNoteOpen(true)}>Add note</Button>
              <Button onClick={() => setKycOpen(true)}>Open review</Button>
            </div>
          </Card>
        </section>
      ) : null}

      {tab === "subscriptions" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="Active" value={String(stats?.active ?? 0)} delta={stats?.topPlan ?? ""} tone="success" />
            <StatCard label="Trialing" value={String(stats?.trialing ?? 0)} delta="Conversion in progress" tone="info" />
            <StatCard label="Paused" value={String(stats?.paused ?? 0)} delta="Awaiting card update" tone="warning" />
            <StatCard label="Canceled (MTD)" value={String(stats?.canceledMtd ?? 0)} delta={`Past due: ${stats?.pastDue ?? 0}`} tone="danger" />
          </section>
          <Card>
            <CardHeader
              title="Plan mix"
              description={`Average revenue per user: ${stats?.arpu ?? "—"} · MRR: ${stats?.mrr ?? "—"}`}
            />
            {planMix.length ? (
              <table className="sp-table">
                <thead>
                  <tr><th>Plan</th><th>Bucket</th><th className="sp-align-right">Subs</th><th className="sp-align-right">Share</th></tr>
                </thead>
                <tbody>
                  {planMix.map((row) => (
                    <tr key={row.plan}>
                      <td><strong>{row.plan}</strong></td>
                      <td>{row.bucket}</td>
                      <td className="sp-align-right">{row.count}</td>
                      <td className="sp-align-right">{row.sharePct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="adm-empty">{subsHook.loading ? "Loading…" : "No active subscriptions."}</p>
            )}
          </Card>
          <Card>
            <CardHeader title="Subscriptions" description="All subscriptions for this merchant, newest first." />
            {subsHook.rows.length ? (
              <table className="sp-table">
                <thead>
                  <tr><th>ID</th><th>Customer</th><th>Plan</th><th>Status</th><th className="sp-align-right">MRR</th><th>Created</th></tr>
                </thead>
                <tbody>
                  {subsHook.rows.map((s) => (
                    <tr key={s.rawId}>
                      <td><code className="adm-code">{s.id}</code></td>
                      <td>{s.customer}</td>
                      <td>{s.plan}</td>
                      <td><Badge tone={s.status === "Active" ? "success" : s.status === "Trialing" ? "info" : s.status === "Past due" ? "danger" : "warning"}>{s.status}</Badge></td>
                      <td className="sp-align-right">{s.mrr}</td>
                      <td>{formatTime(s.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="adm-empty">{subsHook.loading ? "Loading…" : "No subscriptions yet."}</p>
            )}
            <Pagination
              page={subsHook.page}
              pageCount={Math.max(1, Math.ceil(subsHook.total / Math.max(1, subsHook.pageSize)))}
              totalLabel={paginationLabel(subsHook.page, subsHook.pageSize, subsHook.total, "subscriptions")}
              onPageChange={setSubsPage}
            />
          </Card>
        </>
      ) : null}

      {tab === "payments" ? (
        <Card>
          <CardHeader
            title="Payments"
            description="Full history of charge attempts. Refund or replay individual payments."
            action={<Button variant="ghost" icon={<ExternalLink size={14} />} onClick={() => notify({ tone: "info", title: "Export queued", description: `Payment history for ${merchant.name} will be emailed to you shortly.` })}>Export CSV</Button>}
          />
          {paymentsHook.rows.length ? (
            <table className="sp-table">
              <thead>
                <tr><th>Payment</th><th>Customer</th><th>Amount</th><th>Status</th><th>Method</th><th>When</th><th></th></tr>
              </thead>
              <tbody>
                {paymentsHook.rows.map((p) => (
                  <tr key={p.rawId}>
                    <td><code className="adm-code">{p.id}</code></td>
                    <td>{p.customer}</td>
                    <td>{p.amount}</td>
                    <td>{paymentBadge(p.status)}</td>
                    <td>{p.method}</td>
                    <td>{formatTime(p.occurredAt)}</td>
                    <td className="sp-align-right">
                      {canOperate ? (
                        <Button variant="ghost" onClick={() => setRefundOpen(p)} icon={<RotateCcw size={14} />}>Refund</Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="adm-empty">{paymentsHook.loading ? "Loading…" : "No payments yet."}</p>
          )}
          <Pagination
            page={paymentsHook.page}
            pageCount={Math.max(1, Math.ceil(paymentsHook.total / Math.max(1, paymentsHook.pageSize)))}
            totalLabel={paginationLabel(paymentsHook.page, paymentsHook.pageSize, paymentsHook.total, "payments")}
            onPageChange={setPaymentsPage}
          />
        </Card>
      ) : null}

      {tab === "webhooks" ? (
        <Card>
          <CardHeader
            title="Webhook deliveries"
            description="All outbound events. Replay on demand and rotate the signing secret."
            action={canRotateMerchantSecret ? <Button icon={<Key size={14} />} onClick={() => setSecretOpen(true)}>Rotate secret</Button> : undefined}
          />
          {webhooksHook.rows.length ? (
            <table className="sp-table">
              <thead>
                <tr><th>Event</th><th>Endpoint</th><th>Status</th><th className="sp-align-right">Attempts</th><th className="sp-align-right">HTTP</th><th>When</th><th></th></tr>
              </thead>
              <tbody>
                {webhooksHook.rows.map((w) => (
                  <tr key={w.rawId}>
                    <td><code className="adm-code">{w.event}</code></td>
                    <td><span className="adm-muted">{w.endpoint}</span></td>
                    <td><Badge tone={w.status === "Delivered" ? "success" : w.status === "Retrying" ? "warning" : "danger"}>{w.status}</Badge></td>
                    <td className="sp-align-right">{w.attempts}</td>
                    <td className="sp-align-right">{w.responseCode}</td>
                    <td>{formatTime(w.lastAttempt)}</td>
                    <td className="sp-align-right">
                      {canOperate ? (
                        <Button
                          variant="ghost"
                          icon={<RefreshCw size={14} />}
                          disabled={replayingId === w.rawId}
                          onClick={async () => {
                            setReplayingId(w.rawId);
                            try {
                              await retryWebhook({ deliveryId: w.rawId });
                              notify({ tone: "success", title: "Replay scheduled", description: `${w.event} re-emitted to ${w.endpoint}.` });
                              await webhooksHook.reload?.();
                            } catch (err) {
                              notify({ tone: "danger", title: "Replay failed", description: err instanceof Error ? err.message : "Could not requeue delivery." });
                            } finally {
                              setReplayingId(null);
                            }
                          }}
                        >
                          {replayingId === w.rawId ? "Replaying…" : "Replay"}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="adm-empty">{webhooksHook.loading ? "Loading…" : "No webhook deliveries yet."}</p>
          )}
          <Pagination
            page={webhooksHook.page}
            pageCount={Math.max(1, Math.ceil(webhooksHook.total / Math.max(1, webhooksHook.pageSize)))}
            totalLabel={paginationLabel(webhooksHook.page, webhooksHook.pageSize, webhooksHook.total, "deliveries")}
            onPageChange={setWebhooksPage}
          />
        </Card>
      ) : null}

      {tab === "config" ? (
        <section className="sp-panel-layout">
          <Card>
            <CardHeader
              title="Limits & policy"
              description="Per-merchant overrides on top of platform defaults."
              action={canEditMerchantConfig ? <Button icon={<Sliders size={14} />} onClick={() => setConfigOpen(true)}>Edit</Button> : undefined}
            />
            {cfg ? (
              <dl className="adm-defs">
                <div><dt>Monthly volume cap</dt><dd>{cfg.limits.monthlyVolumeCap}</dd></div>
                <div><dt>Max ticket size</dt><dd>{cfg.limits.maxTicketSize}</dd></div>
                <div><dt>High-risk MCC</dt><dd>{cfg.limits.highRiskMcc ? "Yes" : "No"}</dd></div>
                <div><dt>Payout cadence</dt><dd>{cfg.limits.payoutCadence}</dd></div>
                <div><dt>Notifications</dt><dd>{cfg.limits.notificationChannel}</dd></div>
                <div><dt>Retry policy</dt><dd>{`${cfg.retryPolicy.attempts} attempts · ${cfg.retryPolicy.backoff} · ${cfg.retryPolicy.cooldownHours}h`}</dd></div>
              </dl>
            ) : (
              <p className="adm-empty">{cfgHook.loading ? "Loading config…" : cfgHook.error ?? "Config unavailable."}</p>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Feature flags"
              description="Toggle capabilities for this merchant only. Owner-only writes; changes are audited."
            />
            {cfg ? (
              <ul className="adm-toggle-list">
                {cfg.featureFlags.map((f) => (
                  <li key={f.key} className="adm-toggle-row">
                    <input
                      type="checkbox"
                      checked={f.enabled}
                      aria-label={f.label}
                      disabled={cfgHook.saving}
                      onChange={async (e) => {
                        const next = e.target.checked;
                        try {
                          await cfgHook.setFlag(f.key, next);
                          notify({
                            tone: "success",
                            title: `${f.label} ${next ? "enabled" : "disabled"}`,
                            description: `Feature flag updated for ${merchant.name}.`
                          });
                        } catch (err) {
                          notify({
                            tone: "danger",
                            title: "Could not update flag",
                            description: err instanceof Error ? err.message : "Try again."
                          });
                        }
                      }}
                    />
                    <div className="adm-toggle-meta">
                      <strong>{f.label}</strong>
                      <small className="adm-muted">{f.description}</small>
                    </div>
                    <Badge tone={f.enabled ? "success" : "neutral"}>{f.enabled ? "On" : "Off"}</Badge>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="adm-empty">{cfgHook.loading ? "Loading flags…" : "No flag catalog available."}</p>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Webhook endpoints"
              description="HTTPS targets receiving events for this merchant."
              action={<Button variant="ghost" icon={<Webhook size={14} />} onClick={() => notify({ tone: "info", title: "Add endpoint", description: `Configure a new webhook endpoint for ${merchant.name}.` })}>Add endpoint</Button>}
            />
            {cfg && cfg.webhookEndpoints.length ? (
              <ul className="adm-endpoint-list">
                {cfg.webhookEndpoints.map((e) => (
                  <li key={e.id} className="adm-endpoint-row">
                    <div>
                      <strong>{e.url}</strong>
                      <small>{e.events.join(", ") || "all events"}</small>
                    </div>
                    <Badge tone={e.status === "Active" ? "success" : "neutral"}>{e.status}</Badge>
                    <Button
                      variant="ghost"
                      icon={<Trash2 size={14} />}
                      aria-label="Remove endpoint"
                      onClick={async () => {
                        const ok = await confirm({
                          title: "Remove webhook endpoint?",
                          description: `${e.url} will stop receiving events immediately. Queued deliveries are dropped.`,
                          confirmLabel: "Remove endpoint",
                          destructive: true
                        });
                        if (!ok) return;
                        notify({ tone: "danger", title: "Endpoint removed", description: `${e.url} no longer receives events for ${merchant.name}.` });
                      }}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="adm-empty">No webhook endpoints configured.</p>
            )}
          </Card>

          <Card tone="mint">
            <CardHeader title="Danger zone" description="Destructive merchant operations." />
            {canOperate ? (
              <div className="adm-danger-row">
                <div>
                  <strong>Suspend merchant</strong>
                  <p>Immediately disable billing and webhooks. Customers see a maintenance state.</p>
                </div>
                <Button variant="danger" onClick={() => setSuspendOpen(true)}>Suspend</Button>
              </div>
            ) : null}
            {canForceCloseSubscription ? (
              <div className="adm-danger-row">
                <div>
                  <strong>Force account closure</strong>
                  <p>Cancel all subscriptions, refund credit balance, and lock the workspace.</p>
                </div>
                <Button
                  variant="danger"
                  disabled={closing}
                  onClick={async () => {
                    const ok = await confirm({
                      title: `Force-close ${merchant.name}?`,
                      description: "All subscriptions will be canceled, credit balance refunded, and the workspace locked. This cannot be undone.",
                      confirmLabel: "Close account",
                      destructive: true
                    });
                    if (!ok) return;
                    setClosing(true);
                    try {
                      await forceClose({ note: "Force-closed via merchant detail page." });
                      notify({ tone: "danger", title: "Account closed", description: `${merchant.name} has been locked. All subscriptions canceled.` });
                    } catch (err) {
                      notify({ tone: "danger", title: "Could not close account", description: err instanceof Error ? err.message : "Force-close failed. Owner role required." });
                    } finally {
                      setClosing(false);
                    }
                  }}
                >
                  {closing ? "Closing…" : "Close account"}
                </Button>
              </div>
            ) : null}
          </Card>
        </section>
      ) : null}

      {tab === "audit" ? (
        <Card>
          <CardHeader title="Merchant audit log" description="Every administrative action affecting this account." />
          {auditHook.rows.length ? (
            <>
              <ul className="adm-timeline">
                {auditHook.rows.map((a) => (
                  <li key={a.rawId} className="adm-timeline__item">
                    <span className="adm-timeline__dot" aria-hidden="true" />
                    <div>
                      <strong>{a.action}</strong>
                      <p>{a.detail}</p>
                      <small>{a.actor} · {formatTime(a.occurredAt)}</small>
                    </div>
                  </li>
                ))}
              </ul>
              <Pagination
                page={auditHook.page}
                pageCount={Math.max(1, Math.ceil(auditHook.total / Math.max(1, auditHook.pageSize)))}
                totalLabel={paginationLabel(auditHook.page, auditHook.pageSize, auditHook.total, "events")}
                onPageChange={setAuditPage}
              />
            </>
          ) : (
            <p className="adm-empty">{auditHook.loading ? "Loading…" : "No audit events for this merchant yet."}</p>
          )}
        </Card>
      ) : null}

      {/* ---------------- Modals & Sheets ---------------- */}
      <Modal
        open={suspendOpen}
        title={`Suspend ${merchant.name}?`}
        description="Billing, webhooks, and the customer portal will pause within 30 seconds."
        onClose={() => setSuspendOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setSuspendOpen(false)}>Cancel</Button>
            <Button
              variant="danger"
              onClick={async () => {
                try {
                  await suspend({ reason: suspendReason, note: suspendNote });
                  setSuspendOpen(false);
                  setSuspendNote("");
                  notify({ tone: "danger", title: `${merchant.name} suspended`, description: "Billing, webhooks, and the customer portal will pause within 30 seconds." });
                } catch (err) {
                  notify({ tone: "danger", title: "Suspend failed", description: err instanceof Error ? err.message : "Could not suspend merchant." });
                }
              }}
            >
              Yes, suspend
            </Button>
          </>
        }
      >
        <Field label="Reason for suspension">
          <SelectInput value={suspendReason} onChange={(e) => setSuspendReason(e.target.value)}>
            <option value="risk">Risk / chargeback ratio</option>
            <option value="kyc">KYC failure</option>
            <option value="ops">Operational issue</option>
            <option value="legal">Legal / compliance request</option>
          </SelectInput>
        </Field>
        <Field label="Internal note (audit trail)">
          <TextInput value={suspendNote} onChange={(e) => setSuspendNote(e.target.value)} placeholder="Why is this merchant being suspended?" />
        </Field>
        <p className="adm-modal-warn"><AlertTriangle size={14} /> The merchant&rsquo;s owner will be emailed once you confirm.</p>
      </Modal>

      <Modal
        open={reinstateOpen}
        title={`Reinstate ${merchant.name}?`}
        description="Resume billing and webhook delivery. Pending invoices will retry on the next cron tick."
        onClose={() => setReinstateOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setReinstateOpen(false)}>Cancel</Button>
            <Button
              onClick={async () => {
                try {
                  await reactivate({ note: reinstateNote });
                  setReinstateOpen(false);
                  setReinstateNote("");
                  notify({ tone: "success", title: `${merchant.name} reinstated`, description: "Billing and webhook delivery have resumed. Pending invoices retry on the next cron tick." });
                } catch (err) {
                  notify({ tone: "danger", title: "Reactivation failed", description: err instanceof Error ? err.message : "Could not reactivate merchant." });
                }
              }}
            >
              Reinstate
            </Button>
          </>
        }
      >
        <Field label="Reinstatement note">
          <TextInput value={reinstateNote} onChange={(e) => setReinstateNote(e.target.value)} placeholder="Reference ticket or compliance approval" />
        </Field>
      </Modal>

      <Modal
        open={kycOpen}
        title="Re-run KYC review"
        description="Triggers a fresh BVN + sanctions check and reopens the documentation queue."
        onClose={() => setKycOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setKycOpen(false)}>Cancel</Button>
            <Button
              disabled={kycSubmitting}
              onClick={async () => {
                setKycSubmitting(true);
                try {
                  await runKycReview({ level: kycLevel, notes: `Review re-run; assignee: ${kycReviewer}.` });
                  setKycOpen(false);
                  notify({ tone: "info", title: "KYC review re-opened", description: `BVN + sanctions check queued for ${merchant.name}.` });
                } catch (err) {
                  notify({ tone: "danger", title: "Could not re-run KYC", description: err instanceof Error ? err.message : "KYC review failed." });
                } finally {
                  setKycSubmitting(false);
                }
              }}
              icon={<ShieldCheck size={14} />}
            >
              {kycSubmitting ? "Running…" : "Run review"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Tier target">
            <SelectInput value={kycLevel} onChange={(e) => setKycLevel(e.target.value)}>
              <option>Tier 1</option>
              <option>Tier 2</option>
              <option>Tier 3</option>
            </SelectInput>
          </Field>
          <Field label="Assignee">
            <SelectInput value={kycReviewer} onChange={(e) => setKycReviewer(e.target.value)}>
              <option>Ada Okafor</option>
              <option>Tunde Martins</option>
              <option>Zainab Musa</option>
            </SelectInput>
          </Field>
        </div>
        <Field label="Documents to re-collect">
          <div className="adm-checklist">
            <label><input type="checkbox" defaultChecked /> Director ID</label>
            <label><input type="checkbox" /> Bank statement</label>
            <label><input type="checkbox" /> Utility bill</label>
            <label><input type="checkbox" /> TIN certificate</label>
          </div>
        </Field>
      </Modal>

      <Modal
        open={secretOpen}
        title="Rotate webhook signing secret"
        description="Generates a new HMAC key. The previous key is honored for 24h to ease rollover."
        onClose={() => setSecretOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setSecretOpen(false)}>Cancel</Button>
            <Button
              disabled={secretSubmitting}
              onClick={async () => {
                setSecretSubmitting(true);
                try {
                  const res = await rotateWebhookSecret({ gracePeriod: secretGrace });
                  setSecretOpen(false);
                  notify({ tone: "warning", title: "Webhook secret rotated", description: `New fingerprint ${res.fingerprint}. Previous key honored for ${res.gracePeriod}.` });
                } catch (err) {
                  notify({ tone: "danger", title: "Could not rotate secret", description: err instanceof Error ? err.message : "Owner role required to rotate." });
                } finally {
                  setSecretSubmitting(false);
                }
              }}
              icon={<Key size={14} />}
            >
              {secretSubmitting ? "Rotating…" : "Rotate now"}
            </Button>
          </>
        }
      >
        <p>Endpoint: <code className="adm-code">{cfg?.webhookEndpoints[0]?.url ?? "—"}</code></p>
        <Field label="Grace period">
          <SelectInput value={secretGrace} onChange={(e) => setSecretGrace(e.target.value)}>
            <option value="0">None (cut over immediately)</option>
            <option value="6h">6 hours</option>
            <option value="24h">24 hours</option>
            <option value="72h">72 hours</option>
          </SelectInput>
        </Field>
      </Modal>

      <Modal
        open={!!refundOpen}
        title={`Refund ${refundOpen?.id ?? ""}?`}
        description={`Charge of ${refundOpen?.amount ?? ""} to ${refundOpen?.customer ?? ""}.`}
        onClose={() => setRefundOpen(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRefundOpen(null)}>Cancel</Button>
            <Button
              variant="danger"
              disabled={refundSubmitting}
              onClick={async () => {
                if (!refundOpen) return;
                setRefundSubmitting(true);
                try {
                  await refundPayment({ paymentId: refundOpen.rawId ?? refundOpen.id, reason: refundReason, note: refundNote });
                  const id = refundOpen.id;
                  const amount = refundAmount || refundOpen.amount;
                  setRefundOpen(null);
                  notify({ tone: "warning", title: "Refund issued", description: `${amount} refunded for ${id}. Customer will receive a confirmation.` });
                  await paymentsHook.reload?.();
                } catch (err) {
                  notify({ tone: "danger", title: "Refund failed", description: err instanceof Error ? err.message : "Could not issue refund." });
                } finally {
                  setRefundSubmitting(false);
                }
              }}
              icon={<RotateCcw size={14} />}
            >
              {refundSubmitting ? "Refunding…" : "Issue refund"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Amount">
            <TextInput value={refundAmount} onChange={(e) => setRefundAmount(e.target.value)} />
          </Field>
          <Field label="Reason">
            <SelectInput value={refundReason} onChange={(e) => setRefundReason(e.target.value)}>
              <option value="duplicate">Duplicate charge</option>
              <option value="fraud">Suspected fraud</option>
              <option value="customer">Customer request</option>
              <option value="other">Other</option>
            </SelectInput>
          </Field>
        </div>
        <Field label="Note for the customer (optional)">
          <TextInput value={refundNote} onChange={(e) => setRefundNote(e.target.value)} placeholder="Will appear on the receipt." />
        </Field>
      </Modal>

      <Modal
        open={noteOpen}
        title="Add internal note"
        description="Visible to platform admins only. Captured in the audit log."
        onClose={() => setNoteOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setNoteOpen(false)}>Cancel</Button>
            <Button
              onClick={async () => {
                if (!noteBody.trim()) {
                  notify({ tone: "warning", title: "Note body required", description: "Please describe what should be captured in the audit trail." });
                  return;
                }
                try {
                  await addNote({ body: noteBody.trim(), visibility: noteVisibility });
                  setNoteOpen(false);
                  setNoteBody("");
                  notify({ tone: "success", title: "Note saved", description: `Internal note added to ${merchant.name}'s audit log.` });
                } catch (err) {
                  notify({ tone: "danger", title: "Could not save note", description: err instanceof Error ? err.message : "Try again." });
                }
              }}
            >
              Save note
            </Button>
          </>
        }
      >
        <Field label="Visibility">
          <SegmentedControl
            label="Visibility"
            value={noteVisibility}
            onChange={setNoteVisibility}
            items={[
              { label: "All admins", value: "all" },
              { label: "Operations", value: "ops" },
              { label: "Compliance", value: "comp" }
            ]}
          />
        </Field>
        <Field label="Note">
          <TextInput value={noteBody} onChange={(e) => setNoteBody(e.target.value)} placeholder="What should the next reviewer know?" />
        </Field>
      </Modal>

      <Sheet
        open={configOpen}
        title="Edit limits & policy"
        description={`Per-merchant overrides for ${merchant.name}. Owner-only.`}
        onClose={() => setConfigOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfigOpen(false)}>Cancel</Button>
            <Button
              disabled={cfgHook.saving}
              onClick={async () => {
                try {
                  await cfgHook.update({
                    limits: {
                      monthlyVolumeCapMinor: parseIntOr(editVolMinor, 0),
                      maxTicketMinor: parseIntOr(editTicketMinor, 0),
                      highRiskMcc: editRisk === "yes",
                      payoutCadence: editCadence,
                      notificationChannels: tokenToChannels(editChannels)
                    },
                    retryPolicy: {
                      attempts: parseIntOr(editAttempts, 0),
                      backoff: editBackoff,
                      cooldownHours: parseIntOr(editCooldown, 0)
                    }
                  });
                  setConfigOpen(false);
                  notify({ tone: "success", title: "Limits saved", description: `Per-merchant overrides updated for ${merchant.name}.` });
                } catch (err) {
                  notify({ tone: "danger", title: "Save failed", description: err instanceof Error ? err.message : "Could not update config." });
                }
              }}
            >
              {cfgHook.saving ? "Saving…" : "Save changes"}
            </Button>
          </>
        }
      >
        <div className="adm-form-grid">
          <Field label="Monthly volume cap (minor units)">
            <TextInput value={editVolMinor} onChange={(e) => setEditVolMinor(e.target.value)} inputMode="numeric" />
          </Field>
          <Field label="Max ticket size (minor units)">
            <TextInput value={editTicketMinor} onChange={(e) => setEditTicketMinor(e.target.value)} inputMode="numeric" />
          </Field>
          <Field label="Payout cadence">
            <SelectInput value={editCadence} onChange={(e) => setEditCadence(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="tplus2">T+2</option>
            </SelectInput>
          </Field>
          <Field label="Notification channel">
            <SelectInput value={editChannels} onChange={(e) => setEditChannels(e.target.value)}>
              <option value="email">Email</option>
              <option value="slack">Slack</option>
              <option value="email+slack">Email + Slack</option>
            </SelectInput>
          </Field>
          <Field label="Retry attempts">
            <TextInput value={editAttempts} onChange={(e) => setEditAttempts(e.target.value)} inputMode="numeric" />
          </Field>
          <Field label="Cooldown (hours)">
            <TextInput value={editCooldown} onChange={(e) => setEditCooldown(e.target.value)} inputMode="numeric" />
          </Field>
        </div>
        <Field label="Backoff strategy">
          <SegmentedControl
            label="Backoff strategy"
            value={editBackoff}
            onChange={setEditBackoff}
            items={[
              { label: "Linear", value: "linear" },
              { label: "Exponential", value: "exponential" }
            ]}
          />
        </Field>
        <Field label="High-risk MCC">
          <SegmentedControl
            label="High-risk MCC"
            value={editRisk}
            onChange={setEditRisk}
            items={[
              { label: "Standard", value: "no" },
              { label: "High risk", value: "yes" }
            ]}
          />
        </Field>
        <h3 className="adm-sheet-section">Invite teammate</h3>
        <p className="adm-muted">Bring an internal collaborator into this merchant&rsquo;s view (read-only).</p>
        <div className="adm-form-grid">
          <Field label="Email">
            <TextInput placeholder="name@subpilot.dev" />
          </Field>
          <Field label="Role">
            <SelectInput defaultValue="Read-only">
              <option>Read-only</option>
              <option>Support</option>
              <option>Operator</option>
            </SelectInput>
          </Field>
        </div>
        <Button
          icon={<UserPlus size={14} />}
          onClick={() => notify({ tone: "success", title: "Invitation sent", description: `Read-only invite issued for ${merchant.name}.` })}
        >
          Send invitation
        </Button>
      </Sheet>
    </>
  );
}

// --- Helpers ---------------------------------------------------------------

function paymentBadge(status: string) {
  const tone =
    status === "Captured" ? "success" :
    status === "Failed" ? "danger" :
    status === "Recovered" ? "info" : "warning";
  return <Badge tone={tone}>{status}</Badge>;
}

function paginationLabel(page: number, pageSize: number, total: number, noun: string) {
  if (total === 0) return `0 ${noun}`;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return `Showing ${from}-${to} of ${total} ${noun}`;
}

function formatTime(iso: string) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function parseIntOr(raw: string, fallback: number): number {
  const v = Number.parseInt(String(raw ?? "").replace(/[^\d-]/g, ""), 10);
  return Number.isFinite(v) ? v : fallback;
}

function payoutToToken(label: string): string {
  const s = (label || "").toLowerCase();
  if (s.startsWith("weekly")) return "weekly";
  if (s.startsWith("t+") || s === "tplus2") return "tplus2";
  return "daily";
}

function backoffToToken(label: string): string {
  return (label || "").toLowerCase() === "linear" ? "linear" : "exponential";
}

function channelsToToken(channels: string[] | undefined): string {
  const set = new Set((channels ?? []).map((c) => c.toLowerCase()));
  if (set.has("email") && set.has("slack")) return "email+slack";
  if (set.has("slack")) return "slack";
  return "email";
}

function tokenToChannels(token: string): string[] {
  switch (token) {
    case "slack": return ["slack"];
    case "email+slack": return ["email", "slack"];
    default: return ["email"];
  }
}
