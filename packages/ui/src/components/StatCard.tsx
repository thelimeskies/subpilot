import { Card } from "./Card";
import { Badge, type BadgeTone } from "./Badge";
import "./components.css";

export function StatCard({
  label,
  value,
  delta,
  tone = "neutral"
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: BadgeTone;
}) {
  return (
    <Card className="sp-stat-card">
      <span className="sp-stat-card__label">{label}</span>
      <strong>{value}</strong>
      {delta ? <Badge tone={tone}>{delta}</Badge> : null}
    </Card>
  );
}
