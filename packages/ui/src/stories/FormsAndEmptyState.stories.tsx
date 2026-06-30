import type { Meta, StoryObj } from "@storybook/react";
import { Inbox } from "lucide-react";
import { Field, SelectInput, TextInput } from "../components/Form";
import { Button } from "../components/Button";
import { EmptyState } from "../components/EmptyState";

const meta: Meta = {
  title: "Forms/Forms and Empty States",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const PlanForm: Story = {
  render: () => (
    <form style={{ display: "grid", gap: 16, maxWidth: 480 }}>
      <Field label="Plan name" hint="Visible to merchants and customers.">
        <TextInput placeholder="Growth Monthly" />
      </Field>
      <Field label="Currency">
        <SelectInput defaultValue="NGN">
          <option value="NGN">NGN — Nigerian Naira</option>
          <option value="USD">USD — US Dollar</option>
          <option value="GHS">GHS — Ghanaian Cedi</option>
        </SelectInput>
      </Field>
      <Field label="Amount" hint="Charged every billing cycle.">
        <TextInput type="number" placeholder="24000" />
      </Field>
      <Field label="Trial days" error="Trial cannot exceed 30 days.">
        <TextInput type="number" defaultValue={45} />
      </Field>
      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <Button variant="ghost" type="button">
          Cancel
        </Button>
        <Button type="submit">Save plan</Button>
      </div>
    </form>
  )
};

export const Empty: Story = {
  render: () => (
    <EmptyState
      icon={<Inbox size={32} />}
      title="No subscriptions yet"
      description="Publish a plan and share a checkout link to onboard your first customer."
      action={<Button>Create a plan</Button>}
    />
  )
};
