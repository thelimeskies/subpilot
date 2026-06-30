import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="mer-empty-state">
      <h2>Page not found</h2>
      <p>The page you tried to open does not exist or has been moved.</p>
      <Link to="/" className="mer-card-link">Return to overview</Link>
    </div>
  );
}
