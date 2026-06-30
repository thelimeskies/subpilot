import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "../components/Badge";
import { Card, CardHeader } from "../components/Card";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/Button";

const meta: Meta = {
  title: "Foundations/Badges and Cards",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const Badges: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <Badge tone="neutral">Draft</Badge>
      <Badge tone="info">Trialing</Badge>
      <Badge tone="success">Active</Badge>
      <Badge tone="warning">Past due</Badge>
      <Badge tone="danger">Canceled</Badge>
      <Badge tone="teal">Pilot</Badge>
    </div>
  )
};

export const SurfaceCard: Story = {
  render: () => (
    <div style={{ maxWidth: 480 }}>
      <Card>
        <CardHeader
          title="Plan: Growth Monthly"
          description="₦24,000 every month, 7-day trial"
          action={<Button variant="secondary">Edit</Button>}
        />
        <p>3 active price tiers · 412 subscribers</p>
      </Card>
    </div>
  )
};

export const Tones: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(3, 1fr)" }}>
      <Card tone="surface">
        <CardHeader title="Surface" description="Default white surface." />
      </Card>
      <Card tone="mint">
        <CardHeader title="Mint Wash" description="Contextual panels." />
      </Card>
      <Card tone="ink">
        <CardHeader title="Deep Ink" description="High-emphasis sections." />
      </Card>
    </div>
  )
};

export const Stats: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(3, 1fr)" }}>
      <StatCard label="MRR" value="₦4.2M" delta="+8.4%" tone="success" />
      <StatCard label="Active subs" value="1,284" delta="+34" tone="info" />
      <StatCard label="Past due" value="42" delta="-12" tone="warning" />
    </div>
  )
};
