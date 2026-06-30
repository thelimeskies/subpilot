import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Checkbox, Toggle } from "../components/ChoiceControls";
import { Alert, Toast } from "../components/ToastAlert";

const meta: Meta = {
  title: "Forms/Choice and Feedback",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const Checkboxes: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 12, maxWidth: 360 }}>
      <Checkbox label="Email customer on renewal" description="Sends a receipt 24 hours before charge." />
      <Checkbox label="Allow proration" description="Charge or credit unused time." defaultChecked />
      <Checkbox label="Pause when card fails" />
    </div>
  )
};

export const Toggles: Story = {
  render: () => {
    const [a, setA] = useState(true);
    const [b, setB] = useState(false);
    return (
      <div style={{ display: "grid", gap: 12, maxWidth: 360 }}>
        <Toggle label="Smart retries" description="Adapt retry cadence to card type." checked={a} onChange={setA} />
        <Toggle label="Sandbox mode" description="Use test API keys." checked={b} onChange={setB} />
      </div>
    );
  }
};

export const Alerts: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 12 }}>
      <Alert tone="info" title="Heads up">
        Webhook delivery may be delayed during the maintenance window.
      </Alert>
      <Alert tone="success" title="Plan published">
        Growth Monthly is now available to merchants.
      </Alert>
      <Alert tone="warning" title="Action required">
        4 customers have expiring cards in the next 7 days.
      </Alert>
      <Alert tone="danger" title="Charge failed">
        Insufficient funds on token tok_4f9. Recovery has been queued.
      </Alert>
    </div>
  )
};

export const Toasts: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 12, maxWidth: 360 }}>
      <Toast tone="success" title="Saved" description="Subscription updated." />
      <Toast tone="warning" title="Past due" description="2 customers entered dunning." />
      <Toast tone="danger" title="Sync failed" description="Retrying in 30 seconds." />
    </div>
  )
};
