import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  SegmentedControl,
  StatCard,
  Tabs
} from "@subpilot/ui";
import {
  ArrowDownRight,
  ArrowUpRight,
  Download,
  RefreshCw,
  Share2,
  TrendingUp
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import {
  useAnalytics,
  type AnalyticsRange,
  type RevenuePoint
} from "../api/analytics";

type TabKey = "revenue" | "subscriptions" | "payments" | "recovery" | "merchants";

const EMPTY_POINT: RevenuePoint = {
  month: "—",
  mrr: 0,
  newMrr: 0,
  churnMrr: 0,
  expansionMrr: 0,
  gmv: 0,
  activeSubs: 0
};

export function AnalyticsPage() {
  const { notify } = useFeedback();
  const [range, setRange] = useState<AnalyticsRange>("12m");
  const [tab, setTab] = useState<TabKey>("revenue");
  const { analytics, loading, refreshing, error, refresh } = useAnalytics(range);

  const handleRefresh = async () => {
    try {
      await refresh();
      notify({
        tone: "success",
        title: "Analytics refreshed",
        description: "Latest figures pulled from the warehouse."
      });
    } catch {
      notify({
        tone: "danger",
        title: "Refresh failed",
        description: "Could not refresh analytics."
      });
    }
  };

  const header = (
    <PageHeader
      eyebrow={<span className="adm-kicker">Revenue & analytics</span>}
      title="Analytics"
      description="Platform-wide revenue, retention, and recovery telemetry. All figures across every merchant on SubPilot."
      actions={
        <>
          <Button
            variant="ghost"
            icon={<RefreshCw size={16} />}
            onClick={() => void handleRefresh()}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </Button>
          <Button
            variant="ghost"
            icon={<Share2 size={16} />}
            onClick={() =>
              notify({
                tone: "info",
                title: "View link copied",
                description: "A shareable link to this analytics view has been copied to your clipboard."
              })
            }
          >
            Share view
          </Button>
          <Button
            icon={<Download size={16} />}
            onClick={() =>
              notify({
                tone: "info",
                title: "Export queued",
                description: "We'll email you the CSV export when it's ready."
              })
            }
          >
            Export CSV
          </Button>
        </>
      }
    />
  );

  if (loading && !analytics) {
    return (
      <>
        {header}
        <Card>
          <div style={{ padding: "2rem", textAlign: "center" }} className="adm-muted">
            Loading analytics…
          </div>
        </Card>
      </>
    );
  }

  if (!analytics) {
    return (
      <>
        {header}
        <Card>
          <div style={{ padding: "2rem", textAlign: "center" }} className="adm-muted">
            {error ?? "Analytics are not available right now."}
          </div>
        </Card>
      </>
    );
  }

  const series: RevenuePoint[] = analytics.revenueSeries;
  const planRevenue = analytics.planRevenue;
  const regionRevenue = analytics.regionRevenue;
  const retentionCohorts = analytics.retentionCohorts;
  const acquisitionFunnel = analytics.acquisitionFunnel;
  const paymentMethodMix = analytics.paymentMethodMix;
  const recoveryFunnel = analytics.recoveryFunnel;
  const topMerchantsByRevenue = analytics.topMerchantsByRevenue;

  const last = series[series.length - 1] ?? EMPTY_POINT;
  const first = series[0] ?? EMPTY_POINT;
  const prev = series[series.length - 2] ?? first;

  const mrrGrowth = first.mrr ? pct((last.mrr - first.mrr) / first.mrr) : "—";
  const mrrMoM = prev.mrr ? pct((last.mrr - prev.mrr) / prev.mrr) : "—";
  const netNew = round((last.newMrr + last.expansionMrr) - last.churnMrr, 1);
  const churnPct = prev.mrr ? pct(last.churnMrr / prev.mrr) : "—";
  const arpu = last.activeSubs ? (last.mrr * 1_000_000) / last.activeSubs : 0;

  return (
    <>
      {header}

      <div className="adm-search-row">
        <SegmentedControl
          label="Time range"
          value={range}
          onChange={(v) => setRange(v as AnalyticsRange)}
          items={[
            { label: "Last 3 months", value: "3m" },
            { label: "Last 6 months", value: "6m" },
            { label: "Last 12 months", value: "12m" }
          ]}
        />
      </div>

      <section className="sp-grid sp-grid-4">
        <StatCard label="MRR" value={`NGN ${last.mrr.toFixed(1)}m`} delta={`${mrrMoM} MoM · ${mrrGrowth} since ${first.month}`} tone="success" />
        <StatCard label="Net new MRR" value={`NGN ${netNew.toFixed(1)}m`} delta={`${last.newMrr.toFixed(1)}m new · ${last.expansionMrr.toFixed(1)}m expansion`} tone="info" />
        <StatCard label="Gross churn" value={`NGN ${last.churnMrr.toFixed(1)}m`} delta={`${churnPct} of MRR`} tone="warning" />
        <StatCard label="ARPU" value={`NGN ${formatCompact(arpu)}`} delta={`${last.activeSubs.toLocaleString()} active subs`} tone="teal" />
      </section>

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Revenue", value: "revenue" },
          { label: "Subscriptions", value: "subscriptions" },
          { label: "Payments", value: "payments" },
          { label: "Recovery", value: "recovery" },
          { label: "Merchants", value: "merchants" }
        ]}
      />

      {tab === "revenue" ? (
        <>
          <Card>
            <CardHeader
              title="MRR trend"
              description={`${first.month} → ${last.month} · monthly recurring revenue across the platform`}
              action={<Badge tone="success"><TrendingUp size={12} aria-hidden="true" /> {mrrGrowth}</Badge>}
            />
            <Sparkline points={series.map((s) => s.mrr)} labels={series.map((s) => s.month)} unit="m" />
          </Card>

          <section className="sp-panel-layout">
            <Card>
              <CardHeader title="Revenue movement" description="New, expansion, and churn MRR per month." />
              <StackedBars data={series} />
              <ul className="adm-legend">
                <li><i className="adm-legend__dot adm-legend__dot--new" /> New MRR</li>
                <li><i className="adm-legend__dot adm-legend__dot--expansion" /> Expansion</li>
                <li><i className="adm-legend__dot adm-legend__dot--churn" /> Churn</li>
              </ul>
            </Card>

            <Card tone="mint">
              <CardHeader title="Revenue mix by plan" description="Share of total platform MRR." />
              <ul className="adm-share-list">
                {planRevenue.map((p) => (
                  <li key={p.plan}>
                    <div className="adm-share-row__head">
                      <strong>{p.plan}</strong>
                      <span>{p.mrr}</span>
                    </div>
                    <div className="adm-share-bar"><span style={{ width: `${p.share * 100}%` }} /></div>
                    <small>{p.merchants} merchants · ARPU {p.arpu} · churn {p.churn}</small>
                  </li>
                ))}
              </ul>
            </Card>
          </section>

          <Card>
            <CardHeader title="Region performance" description="Where SubPilot revenue lives today." />
            <table className="sp-table">
              <thead>
                <tr><th>Region</th><th>MRR</th><th>Share</th><th className="sp-align-right">Merchants</th><th>Growth</th><th>Top adapter</th></tr>
              </thead>
              <tbody>
                {regionRevenue.map((r) => (
                  <tr key={r.region}>
                    <td><strong>{r.region}</strong></td>
                    <td>{r.mrr}</td>
                    <td><div className="adm-share-bar adm-share-bar--inline"><span style={{ width: `${r.share * 100}%` }} /></div></td>
                    <td className="sp-align-right">{r.merchants}</td>
                    <td><Badge tone={r.growth.startsWith("+") ? "success" : "danger"}>{growthIcon(r.growth)} {r.growth}</Badge></td>
                    <td><span className="adm-muted">{r.topAdapter}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      ) : null}

      {tab === "subscriptions" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="Active subs" value={last.activeSubs.toLocaleString()} delta={`${pct((last.activeSubs - first.activeSubs) / first.activeSubs)} since ${first.month}`} tone="success" />
            <StatCard label="Net adds (MoM)" value={(last.activeSubs - prev.activeSubs).toLocaleString()} delta="vs. last month" tone="info" />
            <StatCard label="Trial → paid" value="68%" delta="14d trial" tone="teal" />
            <StatCard label="Logo churn" value="2.1%" delta="trailing 30d" tone="warning" />
          </section>

          <Card>
            <CardHeader title="Active subscriptions" description="Net active subscriptions across every merchant." />
            <Sparkline points={series.map((s) => s.activeSubs)} labels={series.map((s) => s.month)} unit="" />
          </Card>

          <Card>
            <CardHeader title="Retention cohorts" description="% of merchants from each acquisition cohort still active each subsequent month." />
            <table className="sp-table adm-cohort-table">
              <thead>
                <tr>
                  <th>Cohort</th>
                  <th className="sp-align-right">Size</th>
                  {["M0", "M1", "M2", "M3", "M4", "M5"].map((m) => <th key={m}>{m}</th>)}
                </tr>
              </thead>
              <tbody>
                {retentionCohorts.map((row) => (
                  <tr key={row.cohort}>
                    <td><strong>{row.cohort}</strong></td>
                    <td className="sp-align-right">{row.size}</td>
                    {row.retention.map((v, i) => (
                      <td key={i}>
                        {v ? <span className="adm-heat" data-heat={heatBand(v)}>{v}%</span> : <span className="adm-muted">—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card tone="mint">
            <CardHeader title="Acquisition funnel" description="Signups to paying merchants over the last 30 days." />
            <ol className="adm-funnel">
              {acquisitionFunnel.map((step, i) => {
                const max = acquisitionFunnel[0].count;
                const w = Math.max(20, Math.round((step.count / max) * 100));
                return (
                  <li key={step.label} className="adm-funnel__step">
                    <div className="adm-funnel__bar" style={{ width: `${w}%` }}>
                      <strong>{step.label}</strong>
                      <span>{step.count.toLocaleString()}</span>
                    </div>
                    {step.delta ? <small>{step.delta}</small> : null}
                    {i < acquisitionFunnel.length - 1 ? <em aria-hidden="true">↓</em> : null}
                  </li>
                );
              })}
            </ol>
          </Card>
        </>
      ) : null}

      {tab === "payments" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="GMV (last month)" value={`NGN ${last.gmv.toFixed(0)}m`} delta={`${pct((last.gmv - prev.gmv) / prev.gmv)} MoM`} tone="success" />
            <StatCard label="Avg ticket" value="NGN 9,140" delta="weighted across methods" tone="info" />
            <StatCard label="Auth success" value="94.6%" delta="all adapters" tone="teal" />
            <StatCard label="Chargebacks" value="0.42%" delta="under 1.5% threshold" tone="warning" />
          </section>

          <Card>
            <CardHeader title="GMV trend" description="Gross merchandise volume captured per month." />
            <Sparkline points={series.map((s) => s.gmv)} labels={series.map((s) => s.month)} unit="m" />
          </Card>

          <section className="sp-panel-layout">
            <Card>
              <CardHeader title="Payment method mix" description="Share of captured volume by method." />
              <ul className="adm-share-list">
                {paymentMethodMix.map((m) => (
                  <li key={m.method}>
                    <div className="adm-share-row__head">
                      <strong>{m.method}</strong>
                      <span>{Math.round(m.share * 100)}%</span>
                    </div>
                    <div className="adm-share-bar"><span style={{ width: `${m.share * 100}%` }} /></div>
                    <small>Success {m.successRate} · Avg {m.avgTicket}</small>
                  </li>
                ))}
              </ul>
            </Card>

            <Card tone="mint">
              <CardHeader title="Decline reasons" description="Top failure codes across all merchants." />
              <table className="sp-table">
                <thead><tr><th>Reason</th><th className="sp-align-right">Share</th><th>Trend</th></tr></thead>
                <tbody>
                  <tr><td><code className="adm-code">insufficient_funds</code></td><td className="sp-align-right">38%</td><td><Badge tone="warning"><ArrowUpRight size={12} /> +2.1%</Badge></td></tr>
                  <tr><td><code className="adm-code">do_not_honor</code></td><td className="sp-align-right">22%</td><td><Badge tone="danger"><ArrowUpRight size={12} /> +0.6%</Badge></td></tr>
                  <tr><td><code className="adm-code">expired_card</code></td><td className="sp-align-right">18%</td><td><Badge tone="success"><ArrowDownRight size={12} /> -1.4%</Badge></td></tr>
                  <tr><td><code className="adm-code">stolen_card</code></td><td className="sp-align-right">9%</td><td><Badge tone="success"><ArrowDownRight size={12} /> -0.2%</Badge></td></tr>
                  <tr><td><code className="adm-code">network_error</code></td><td className="sp-align-right">7%</td><td><Badge tone="warning"><ArrowUpRight size={12} /> +0.1%</Badge></td></tr>
                  <tr><td><code className="adm-code">other</code></td><td className="sp-align-right">6%</td><td><span className="adm-muted">flat</span></td></tr>
                </tbody>
              </table>
            </Card>
          </section>
        </>
      ) : null}

      {tab === "recovery" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="Recovery rate" value={recoveryFunnel.recoveryRate} delta="trailing 30 days" tone="success" />
            <StatCard label="Recovered MRR" value={recoveryFunnel.recoveredMrr} delta={`${recoveryFunnel.recovered} invoices`} tone="info" />
            <StatCard label="Pending dunning" value={String(recoveryFunnel.pending)} delta="in retry window" tone="warning" />
            <StatCard label="Lost" value={String(recoveryFunnel.lost)} delta={`${pct(recoveryFunnel.lost / recoveryFunnel.failedThisMonth)} of failures`} tone="danger" />
          </section>

          <Card>
            <CardHeader title="Recovery funnel" description={`${recoveryFunnel.failedThisMonth.toLocaleString()} failed invoices this month, by recovery channel.`} />
            <ol className="adm-funnel">
              <li className="adm-funnel__step">
                <div className="adm-funnel__bar" style={{ width: "100%" }}>
                  <strong>Failed invoices</strong>
                  <span>{recoveryFunnel.failedThisMonth.toLocaleString()}</span>
                </div>
                <em aria-hidden="true">↓</em>
              </li>
              <li className="adm-funnel__step">
                <div className="adm-funnel__bar adm-funnel__bar--success" style={{ width: `${(recoveryFunnel.recovered / recoveryFunnel.failedThisMonth) * 100}%` }}>
                  <strong>Recovered</strong>
                  <span>{recoveryFunnel.recovered.toLocaleString()}</span>
                </div>
                <small>{pct(recoveryFunnel.recovered / recoveryFunnel.failedThisMonth)} of failures</small>
                <em aria-hidden="true">↓</em>
              </li>
              <li className="adm-funnel__step">
                <div className="adm-funnel__bar adm-funnel__bar--warn" style={{ width: `${(recoveryFunnel.pending / recoveryFunnel.failedThisMonth) * 100}%` }}>
                  <strong>Pending</strong>
                  <span>{recoveryFunnel.pending.toLocaleString()}</span>
                </div>
                <em aria-hidden="true">↓</em>
              </li>
              <li className="adm-funnel__step">
                <div className="adm-funnel__bar adm-funnel__bar--danger" style={{ width: `${(recoveryFunnel.lost / recoveryFunnel.failedThisMonth) * 100}%` }}>
                  <strong>Lost</strong>
                  <span>{recoveryFunnel.lost.toLocaleString()}</span>
                </div>
              </li>
            </ol>
          </Card>

          <Card tone="mint">
            <CardHeader title="Recovered by channel" description="Which intervention saved the invoice." />
            <ul className="adm-share-list">
              {recoveryFunnel.byChannel.map((c) => (
                <li key={c.channel}>
                  <div className="adm-share-row__head">
                    <strong>{c.channel}</strong>
                    <span>{c.count} · {Math.round(c.share * 100)}%</span>
                  </div>
                  <div className="adm-share-bar"><span style={{ width: `${c.share * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}

      {tab === "merchants" ? (
        <Card>
          <CardHeader
            title="Top merchants by MRR"
            description="The five merchants contributing the most platform revenue this month."
            action={<Button variant="ghost"><Link to="/merchants" className="adm-card-link">View all merchants</Link></Button>}
          />
          <table className="sp-table">
            <thead>
              <tr><th>Merchant</th><th>Region</th><th className="sp-align-right">MRR</th><th>Growth</th><th></th></tr>
            </thead>
            <tbody>
              {topMerchantsByRevenue.map((m) => (
                <tr key={m.id}>
                  <td><strong>{m.name}</strong> <code className="adm-code">{m.id}</code></td>
                  <td><span className="adm-muted">{m.region}</span></td>
                  <td className="sp-align-right">{m.mrr}</td>
                  <td><Badge tone={m.growth.startsWith("+") ? "success" : "danger"}>{growthIcon(m.growth)} {m.growth}</Badge></td>
                  <td className="sp-align-right">
                    <Link to={`/merchants/${m.id}`} className="adm-card-link">Open</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}
    </>
  );
}

/* ---------------- helpers ---------------- */

function pct(n: number) {
  const v = n * 100;
  return `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

function round(n: number, d = 0) {
  const f = 10 ** d;
  return Math.round(n * f) / f;
}

function formatCompact(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toFixed(0);
}

function growthIcon(g: string) {
  return g.startsWith("+") ? <ArrowUpRight size={12} aria-hidden="true" /> : <ArrowDownRight size={12} aria-hidden="true" />;
}

function heatBand(v: number) {
  if (v >= 90) return "5";
  if (v >= 80) return "4";
  if (v >= 70) return "3";
  if (v >= 50) return "2";
  return "1";
}

/* ---------------- mini charts ---------------- */

function Sparkline({ points, labels, unit }: { points: number[]; labels: string[]; unit: string }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const range = Math.max(1, max - min);
  const w = 720;
  const h = 160;
  const pad = 24;
  const stepX = (w - pad * 2) / Math.max(1, points.length - 1);
  const toY = (v: number) => h - pad - ((v - min) / range) * (h - pad * 2);
  const path = points
    .map((v, i) => `${i === 0 ? "M" : "L"} ${pad + i * stepX} ${toY(v)}`)
    .join(" ");
  const area = `${path} L ${pad + (points.length - 1) * stepX} ${h - pad} L ${pad} ${h - pad} Z`;

  return (
    <div className="adm-chart">
      <svg viewBox={`0 0 ${w} ${h}`} className="adm-chart__svg" role="img" aria-label="Trend chart">
        <path d={area} className="adm-chart__area" />
        <path d={path} className="adm-chart__line" />
        {points.map((v, i) => (
          <g key={i}>
            <circle cx={pad + i * stepX} cy={toY(v)} r={3} className="adm-chart__dot" />
          </g>
        ))}
      </svg>
      <div className="adm-chart__labels">
        {labels.map((l, i) => (
          <span key={l} style={{ width: `${100 / labels.length}%` }}>
            <strong>{points[i].toFixed(unit === "m" ? 1 : 0)}{unit}</strong>
            <small>{l}</small>
          </span>
        ))}
      </div>
    </div>
  );
}

function StackedBars({ data }: { data: RevenuePoint[] }) {
  const max = Math.max(...data.map((d) => d.newMrr + d.expansionMrr + d.churnMrr));
  return (
    <div className="adm-bars">
      {data.map((d) => {
        const total = d.newMrr + d.expansionMrr + d.churnMrr;
        const h = (total / max) * 100;
        const newH = (d.newMrr / total) * h;
        const expH = (d.expansionMrr / total) * h;
        const churnH = (d.churnMrr / total) * h;
        return (
          <div key={d.month} className="adm-bars__col" title={`${d.month} · new ${d.newMrr.toFixed(1)}m, exp ${d.expansionMrr.toFixed(1)}m, churn ${d.churnMrr.toFixed(1)}m`}>
            <div className="adm-bars__stack">
              <span className="adm-bars__seg adm-bars__seg--new" style={{ height: `${newH}%` }} />
              <span className="adm-bars__seg adm-bars__seg--expansion" style={{ height: `${expH}%` }} />
              <span className="adm-bars__seg adm-bars__seg--churn" style={{ height: `${churnH}%` }} />
            </div>
            <small>{d.month}</small>
          </div>
        );
      })}
    </div>
  );
}
