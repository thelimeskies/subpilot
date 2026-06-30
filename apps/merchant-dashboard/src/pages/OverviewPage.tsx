import { Badge, Button, Card, CardHeader, StatCard } from "@subpilot/ui";
import {
  ActivitySquare,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CreditCard,
  ShieldCheck,
  Webhook
} from "lucide-react";
import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { useMerchantOverview } from "../api/overview";
import { useData } from "../data/store";
import {
  failingEndpoints,
  findCustomerById,
  findInvoiceById,
  formatCurrency,
  formatRelative,
  recentAuditEvents,
  recentRecoveryItems
} from "../data/selectors";

export function OverviewPage() {
  const { notify } = useFeedback();
  const {
    org,
    invoices,
    recoveryItems,
    customers,
    webhookEndpoints,
    auditEvents
  } = useData();
  const { stats, loading: overviewLoading, error: overviewError, reload: reloadOverview } = useMerchantOverview();

  const audit = recentAuditEvents(auditEvents, 6);
  const recovery = recentRecoveryItems(recoveryItems, 5);
  const failing = failingEndpoints(webhookEndpoints);
  const statLoadingValue = overviewLoading ? "Loading..." : "--";

  return (
    <>
      <PageHeader
        eyebrow={`Workspace · ${org.tradingName}`}
        title="Operations overview"
        description="Live view of MRR, recovery, and developer pipeline health for your merchant workspace."
        actions={
          <>
            <Button
              variant="ghost"
              onClick={async () => {
                await reloadOverview({ force: true });
                notify({
                  tone: "success",
                  title: "Snapshot refreshed",
                  description: "Merchant analytics were recomputed from the backend."
                });
              }}
            >
              Refresh snapshot
            </Button>
            <Button
              onClick={() =>
                notify({
                  tone: "success",
                  title: "Subscription drafting opened",
                  description: "Continue from the Subscriptions page to pick a customer and plan."
                })
              }
            >
              Create subscription
            </Button>
          </>
        }
      />

      {overviewError ? (
        <Card>
          <CardHeader
            title="Could not load live metrics"
            description={overviewError}
            action={
              <Button variant="secondary" onClick={() => void reloadOverview({ force: true })}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : null}

      <section className="sp-grid sp-grid-4">
        <StatCard
          label="MRR"
          value={stats?.mrr ?? statLoadingValue}
          delta={stats?.mrrDelta ?? "Live backend value"}
          tone="success"
        />
        <StatCard
          label="Active subscriptions"
          value={stats?.activeSubscriptions ?? statLoadingValue}
          delta={stats?.activeSubscriptionsDelta ?? "Active + trialing"}
          tone="info"
        />
        <StatCard
          label="Revenue at risk"
          value={stats?.revenueAtRisk ?? statLoadingValue}
          delta={stats?.revenueAtRiskDelta ?? "Past-due exposure"}
          tone="warning"
        />
        <StatCard
          label={stats?.raw.recovery_rate_pct ? "Recovery rate" : "Open invoices"}
          value={stats?.recovery ?? statLoadingValue}
          delta={stats?.recoveryDelta ?? "Recovery snapshot"}
          tone="teal"
        />
      </section>

      <section className="sp-panel-layout">
        <Card>
          <CardHeader
            title="Recovery cockpit"
            description="Top failed invoices that need attention before next dunning step."
            action={
              <Link to="/recovery" className="mer-card-link">
                Open recovery <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            }
          />
          <div className="mer-overview-list">
            {recovery.length === 0 ? (
              <p className="mer-empty">All caught up — no invoices in the recovery queue.</p>
            ) : (
              recovery.map((item) => {
                const customer = findCustomerById(customers, item.customerId);
                const invoice = findInvoiceById(invoices, item.invoiceId);
                return (
                  <div key={item.id} className="mer-overview-row">
                    <span className="mer-overview-row__icon" aria-hidden="true">
                      <AlertTriangle size={14} />
                    </span>
                    <div className="mer-entity-cell">
                      <strong>{customer?.name ?? "Unknown customer"}</strong>
                      <small>{invoice?.number ?? item.invoiceId} · attempt {item.attempts}</small>
                    </div>
                    <Badge tone={recoveryTone(item.stage)}>{prettyStage(item.stage)}</Badge>
                    <span className="mer-overview-row__metric">
                      <strong>{formatCurrency(item.amount, org.currency)}</strong>
                      <small>{formatReason(item.reason)}</small>
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </Card>

        <div className="sp-grid">
          <Card tone="mint">
            <CardHeader title="Pipeline health" description="Gateway, dunning, and webhook status." />
            <div className="mer-overview-health">
              <HealthRow
                icon={<ShieldCheck size={16} />}
                label="MFA enforcement"
                value="Required"
                tone="success"
              />
              <HealthRow
                icon={<ActivitySquare size={16} />}
                label="Dunning rules"
                value="4 attempts · 12/24/72h"
                tone="teal"
              />
              <HealthRow
                icon={<CreditCard size={16} />}
                label="Payout bank"
                value={`${org.payoutBank} · ${org.settlementFrequency}`}
                tone="info"
              />
              <HealthRow
                icon={<Webhook size={16} />}
                label="Webhook endpoints"
                value={failing.length > 0 ? `${failing.length} degraded` : "All healthy"}
                tone={failing.length > 0 ? "warning" : "success"}
              />
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Recent activity"
              description="Latest team and system actions on this workspace."
              action={
                <Link to="/settings" className="mer-card-link">
                  Audit log <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              }
            />
            <div className="mer-overview-list">
              {audit.length === 0 ? (
                <p className="mer-empty">No recent activity.</p>
              ) : (
                audit.map((event) => (
                  <div key={event.id} className="mer-overview-row mer-overview-row--compact">
                    <span className="mer-overview-row__icon" aria-hidden="true">
                      <CheckCircle2 size={14} />
                    </span>
                    <div className="mer-entity-cell">
                      <strong>{event.action}</strong>
                      <small>{event.actor} · {event.target}</small>
                    </div>
                    <span className="mer-muted">{formatRelative(event.occurredAt)}</span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </section>
    </>
  );
}

function HealthRow({
  icon,
  label,
  value,
  tone
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: "success" | "teal" | "warning" | "info" | "danger";
}) {
  return (
    <div className="mer-health-row">
      <span aria-hidden="true">{icon}</span>
      <strong>{label}</strong>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function recoveryTone(stage: string): "warning" | "danger" | "info" {
  switch (stage) {
    case "manual_review":
      return "danger";
    case "paused":
      return "info";
    default:
      return "warning";
  }
}

function prettyStage(stage: string): string {
  switch (stage) {
    case "retry_queue":
      return "Retry queue";
    case "manual_review":
      return "Manual review";
    case "paused":
      return "Paused";
    default:
      return stage;
  }
}

function formatReason(reason: string): string {
  return reason
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
