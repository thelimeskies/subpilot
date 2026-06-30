import { Link } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowLeft } from "lucide-react";

export function NotFoundPage() {
  return (
    <section className="lp-notfound">
      <div className="lp-container">
        <span className="lp-notfound__code lp-mono">404</span>
        <h1>This page hasn't been provisioned.</h1>
        <p>
          The route you tried doesn't exist. Try the home page, or jump straight into the console.
        </p>
        <div className="lp-notfound__actions">
          <Link to="/">
            <Button variant="secondary" icon={<ArrowLeft size={16} />}>
              Back to home
            </Button>
          </Link>
          <a href="/merchant">
            <Button>Open the console</Button>
          </a>
        </div>
      </div>
    </section>
  );
}
