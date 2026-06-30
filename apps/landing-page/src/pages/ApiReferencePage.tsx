import { RedocStandalone } from "redoc";
import { Link } from "react-router-dom";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";

export function ApiReferencePage() {
  return (
    <>
      <header className="lp-redoc__topbar">
        <div className="lp-container lp-redoc__topbar-inner">
          <div className="lp-redoc__crumbs">
            <Link to="/developers" className="lp-redoc__back">
              <ArrowLeft size={14} aria-hidden="true" />
              <span>Developers</span>
            </Link>
            <em aria-hidden="true">/</em>
            <span>API reference</span>
          </div>
          <div className="lp-redoc__actions">
            <a className="lp-redoc__action" href="/openapi.yaml" download>
              <Download size={14} aria-hidden="true" />
              <span>Download spec</span>
            </a>
            <Link className="lp-redoc__action" to="/developers/webhooks">
              <ExternalLink size={14} aria-hidden="true" />
              <span>Webhooks</span>
            </Link>
          </div>
        </div>
      </header>

      <div className="lp-redoc">
        <RedocStandalone
          specUrl="/openapi.yaml"
          options={{
            scrollYOffset: 56,
            hideDownloadButton: false,
            disableSearch: false,
            expandResponses: "200,201",
            expandSingleSchemaField: true,
            jsonSampleExpandLevel: 2,
            menuToggle: true,
            nativeScrollbars: true,
            theme: {
              colors: {
                primary: { main: "#0F766E" },
                success: { main: "#0E7C5E" },
                warning: { main: "#B45309" },
                error: { main: "#B42318" },
                text: { primary: "#0B1720", secondary: "#4B5965" },
                http: {
                  get: "#0F766E",
                  post: "#0E7C5E",
                  put: "#1F6FEB",
                  patch: "#9333EA",
                  delete: "#B42318"
                }
              },
              typography: {
                fontSize: "14px",
                lineHeight: "1.55",
                fontFamily:
                  "'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                headings: {
                  fontFamily:
                    "'Nunito Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                  fontWeight: "700"
                },
                code: {
                  fontFamily:
                    "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: "13px",
                  backgroundColor: "rgba(15, 118, 110, 0.08)",
                  color: "#0B1720"
                }
              },
              sidebar: {
                backgroundColor: "#F6FBF8",
                width: "280px",
                textColor: "#0B1720"
              },
              rightPanel: {
                backgroundColor: "#0B1720",
                textColor: "#E6F4EE",
                width: "40%"
              },
              codeBlock: {
                backgroundColor: "#091016"
              }
            }
          }}
        />
      </div>
    </>
  );
}
