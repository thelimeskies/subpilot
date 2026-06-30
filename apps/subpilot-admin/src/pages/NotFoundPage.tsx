import { Link } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowLeft } from "lucide-react";

export function NotFoundPage() {
  return (
    <div className="adm-empty-state">
      <span className="adm-kicker">404</span>
      <h2>This page took an unscheduled detour.</h2>
      <p>The route you followed doesn&rsquo;t exist in the SubPilot admin console.</p>
      <Link to="/">
        <Button icon={<ArrowLeft size={16} />}>Back to overview</Button>
      </Link>
    </div>
  );
}
