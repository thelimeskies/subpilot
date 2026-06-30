import { Badge, Button, Card, CardHeader, StatCard } from "@subpilot/ui";
import { Activity, ArrowUpRight, CreditCard, ShieldCheck, Webhook } from "lucide-react";
import { Link } from "react-router-dom";
import { payments, webhooks } from "../data/seed";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { useOverview } from "../api/overview";
import { useMerchants } from "../api/merchants";
import { usePlatformPermissions } from "../auth/AuthContext";

export function OverviewPage() {
  const { notify } = useFeedback();
  const { canEditMerchantConfig } = usePlatformPermissions();
  const { stats, loading, error, reload } = useOverview();
  const { rows: merchantRows, loading: merchantsLoading, error: merchantsError } = useMerchants({ pageSize: 50 });
  const failingMerchants = merchantRows.filter((m) => m.status !== "Healthy").slice(0, 5);
  const recentPayments = payments.slice(0, 4);
  const retrying = webhooks.filter((w) => w.status !== "Delivered");

  return (
    <>
      <PageHeader
        eyebrow="Platform operations"
        title="Merchant control center"
        description="Live snapshot of merchant health, recurring volume, recovery posture, and gateway adapter readiness across SubPilot."
        actions={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                void reload({ force: true });
                notify({
                  tone: "info",
                  title: "Refreshing snapshot",
                  description: "Recomputing the cross-tenant overview from live data."
                });
              }}
            >
              Refresh
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                notify({
                  tone: "info",
                  title: "Export queued",
                  description: "Platform snapshot is being prepared. We'll email you the CSV when it's ready."
                })
              }
            >
              Export
            </Button>
            {canEditMerchantConfig ? (
              <Button
                onClick={() =>
                  notify({
                    tone: "success",
                    title: "Merchant onboarding opened",
                    description: "Continue from the merchants page to invite a new merchant."
                  })
                }
              >
                New merchant
              </Button>
            ) : null}
          </>
        }
      />

      {error ? (
        <Card>
          <CardHeader title="Could not load overview" description={error} />
        </Card>
      ) : null}

      <section className="sp-grid sp-grid-4">
        <StatCard
          label="Live merchants"
          value={loading || !stats ? "—" : String(stats.liveMerchants)}
          delta={stats?.liveMerchantsDelta ?? "Loading…"}
          tone="success"
        />
        <StatCard
          label="Platform MRR"
          value={loading || !stats ? "—" : stats.mrr}
          delta={stats?.mrrDelta ?? "Loading…"}
          tone="success"
        />
        <StatCard
          label="Revenue at risk"
          value={loading || !stats ? "—" : stats.revenueAtRisk}
          delta={stats?.revenueAtRiskDelta ?? "Loading…"}
          tone="warning"
        />
        <StatCard
          label="Webhook health"
          value={loading || !stats ? "—" : stats.webhookHealth}
          delta={stats?.webhookHealthDelta ?? "Loading…"}
          tone="teal"
        />
      </section>

      <section className="sp-panel-layout">
        <Card>
          <CardHeader
            title="Risk queue"
            description="Merchants needing platform attention before next billing cycle."
            action={
              <Link to="/merchants" className="adm-card-link">
                Open merchants <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            }
          />
          <div className="adm-risk-list">
            {failingMerchants.map((merchant) => (
              <Link key={merchant.id} to={`/merchants/${merchant.id}`} className="adm-risk-row">
                <div>
                  <strong>{merchant.name}</strong>
                  <small>{merchant.id} · {merchant.region}</small>
                </div>
                <Badge tone={merchant.status === "Suspended" ? "danger" : "warning"}>{merchant.status}</Badge>
                <span className="adm-risk-row__metric">
                  <strong>{merchant.failedInvoices}</strong>
                  <small>failed</small>
                </span>
                <span className="adm-risk-row__metric">
                  <strong>{merchant.recoveryRate}</strong>
                  <small>recovery</small>
                </span>
              </Link>
            ))}
            {!merchantsLoading && failingMerchants.length === 0 ? (
              <p className="adm-empty">
                {merchantsError ?? "All merchants healthy. Nothing to escalate."}
              </p>
            ) : null}
            {merchantsLoading && failingMerchants.length === 0 ? (
              <p className="adm-empty">Loading merchants…</p>
            ) : null}
          </div>
        </Card>

        <div className="sp-grid">
          <Card tone="mint">
            <CardHeader title="Adapter readiness" description="Gateway adapter status by environment." />
            <div className="adm-health-grid">
              <HealthRow icon={<ShieldCheck size={16} />} label="Webhook signatures" value="Verified" tone="success" />
              <HealthRow icon={<Activity size={16} />} label="Sandbox adapter" value="Ready" tone="teal" />
              <HealthRow icon={<CreditCard size={16} />} label="Tokenized charges" value="Monitoring" tone="warning" />
              <HealthRow icon={<Webhook size={16} />} label="Outbound retries" value={`${retrying.length} in flight`} tone="info" />
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Recent payments"
              description="Last few platform-wide charges across adapters."
              action={
                <Link to="/payments" className="adm-card-link">
                  All payments <ArrowUpRight size={14} aria-hidden="true" />
                </Link>
              }
            />
            <div className="adm-event-list">
              {recentPayments.map((payment) => (
                <div key={payment.id} className="adm-event-row">
                  <span className="adm-event-row__icon"><CreditCard size={14} aria-hidden="true" /></span>
                  <div>
                    <strong>{payment.merchant}</strong>
                    <small>{payment.amount} · {payment.method}</small>
                  </div>
                  <Badge tone={paymentTone(payment.status)}>{payment.status}</Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </section>
    </>
  );
}

function HealthRow({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: string; tone: "success" | "teal" | "warning" | "info" }) {
  return (
    <div className="adm-health-row">
      <span>{icon}</span>
      <strong>{label}</strong>
      <Badge tone={tone}>{value}</Badge>
    </div>
  );
}

function paymentTone(status: string): "success" | "danger" | "warning" | "info" {
  switch (status) {
    case "Captured":
      return "success";
    case "Failed":
      return "danger";
    case "Recovered":
      return "info";
    default:
      return "warning";
  }
}
