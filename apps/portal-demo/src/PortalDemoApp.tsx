import { useMemo, useState } from "react";
import { SubPilotPortal, createSubPilotPortalClient, type PortalData } from "@subpilot/portal-js";

const DEFAULT_TOKEN = "";
const DEFAULT_KEY = "pk_test_local";
const DEFAULT_API_BASE = "/api/v1";

export function PortalDemoApp() {
  const [portalToken, setPortalToken] = useState(() => localStorage.getItem("subpilot_demo_token") ?? DEFAULT_TOKEN);
  const [publishableKey, setPublishableKey] = useState(() => localStorage.getItem("subpilot_demo_key") ?? DEFAULT_KEY);
  const [apiBaseUrl, setApiBaseUrl] = useState(() => localStorage.getItem("subpilot_demo_api_base") ?? DEFAULT_API_BASE);
  const [activeToken, setActiveToken] = useState(portalToken);
  const [activeKey, setActiveKey] = useState(publishableKey);
  const [activeApiBase, setActiveApiBase] = useState(apiBaseUrl);
  const [displayMode, setDisplayMode] = useState<"inline" | "modal">("inline");
  const [portalOpen, setPortalOpen] = useState(true);
  const [probeResult, setProbeResult] = useState<string>("Not checked yet");
  const [probing, setProbing] = useState(false);

  const installSnippet = "npm install @subpilot/portal-js";
  const componentSnippet = useMemo(() => `import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingPortal({ portalToken }) {
  return (
    <SubPilotPortal
      publishableKey="${publishableKey || "pk_test_..."}"
      token={portalToken}
      apiBaseUrl="${apiBaseUrl || "/api/v1"}"
      displayMode="${displayMode}"
      open={portalOpen}
      showCloseButton
      closeLabel="Done"
      onClose={() => setPortalOpen(false)}
    />
  );
}`, [apiBaseUrl, displayMode, publishableKey]);

  const clientSnippet = useMemo(() => `import { createSubPilotPortalClient } from "@subpilot/portal-js";

const portal = createSubPilotPortalClient({
  publishableKey: "${publishableKey || "pk_test_..."}",
  apiBaseUrl: "${apiBaseUrl || "/api/v1"}"
});

const data = await portal.loadPortal(portalToken);`, [apiBaseUrl, publishableKey]);

  function applyConfig() {
    localStorage.setItem("subpilot_demo_token", portalToken);
    localStorage.setItem("subpilot_demo_key", publishableKey);
    localStorage.setItem("subpilot_demo_api_base", apiBaseUrl);
    setActiveToken(portalToken.trim());
    setActiveKey(publishableKey.trim());
    setActiveApiBase(apiBaseUrl.trim() || DEFAULT_API_BASE);
    setPortalOpen(true);
  }

  async function probeClient() {
    setProbing(true);
    setProbeResult("Checking portal context...");
    try {
      const client = createSubPilotPortalClient({
        publishableKey: publishableKey.trim(),
        apiBaseUrl: apiBaseUrl.trim() || DEFAULT_API_BASE
      });
      const data: PortalData = await client.loadPortal(portalToken.trim());
      setProbeResult(`${data.merchant.name}: ${data.invoices.length} invoices, ${data.subscriptions.length} subscriptions, ${data.paymentMethods.length} payment methods`);
    } catch (err) {
      setProbeResult(err instanceof Error ? err.message : "Could not load portal context");
    } finally {
      setProbing(false);
    }
  }

  return (
    <main className="demo-shell">
      <section className="demo-console">
        <div className="demo-console__intro">
          <span>SubPilot portal package demo</span>
          <h1>Embedded customer billing portal</h1>
          <p>
            This sample app imports <code>@subpilot/portal-js</code>, passes a publishable key and portal token,
            then renders the same portal merchants can use in their own frontend.
          </p>
        </div>

        <div className="demo-controls" aria-label="Portal demo controls">
          <label>
            <span>Publishable key</span>
            <input value={publishableKey} onChange={(event) => setPublishableKey(event.target.value)} spellCheck={false} />
          </label>
          <label>
            <span>Portal token</span>
            <input value={portalToken} onChange={(event) => setPortalToken(event.target.value)} spellCheck={false} />
          </label>
          <label>
            <span>API base URL</span>
            <input value={apiBaseUrl} onChange={(event) => setApiBaseUrl(event.target.value)} spellCheck={false} />
          </label>
          <label>
            <span>Presentation</span>
            <select value={displayMode} onChange={(event) => setDisplayMode(event.target.value as "inline" | "modal")}>
              <option value="inline">Inline</option>
              <option value="modal">Modal</option>
            </select>
          </label>
          <div className="demo-actions">
            <button type="button" onClick={applyConfig}>Render portal</button>
            {displayMode === "modal" && !portalOpen ? (
              <button type="button" className="demo-button-secondary" onClick={() => setPortalOpen(true)}>Open modal</button>
            ) : null}
            <button type="button" className="demo-button-secondary" onClick={() => void probeClient()} disabled={probing}>
              {probing ? "Checking..." : "Probe client"}
            </button>
          </div>
        </div>

        <div className="demo-status">
          <strong>Client helper result</strong>
          <span>{probeResult}</span>
        </div>

        <div className="demo-snippets">
          <Snippet title="Install" value={installSnippet} />
          <Snippet title="React component" value={componentSnippet} />
          <Snippet title="Client helper" value={clientSnippet} />
        </div>
      </section>

      <section className="demo-preview" aria-label="Embedded portal preview">
        <SubPilotPortal
          key={`${activeKey}:${activeToken}:${activeApiBase}`}
          publishableKey={activeKey}
          token={activeToken}
          apiBaseUrl={activeApiBase}
          displayMode={displayMode}
          open={portalOpen}
          showCloseButton={displayMode === "modal"}
          closeLabel="Done"
          onClose={() => setPortalOpen(false)}
          onLoaded={(data) => {
            setProbeResult(`${data.merchant.name}: portal rendered`);
          }}
          onError={(error) => {
            setProbeResult(error.message);
          }}
        />
      </section>
    </main>
  );
}

function Snippet({ title, value }: { title: string; value: string }) {
  async function copy() {
    await navigator.clipboard?.writeText(value).catch(() => undefined);
  }

  return (
    <section className="demo-snippet">
      <div>
        <strong>{title}</strong>
        <button type="button" onClick={() => void copy()}>Copy</button>
      </div>
      <pre>{value}</pre>
    </section>
  );
}
