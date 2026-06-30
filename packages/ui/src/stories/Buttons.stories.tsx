import type { Meta, StoryObj } from "@storybook/react";
import { ArrowRight, Plus } from "lucide-react";
import { Button } from "../components/Button";

const meta: Meta<typeof Button> = {
  title: "Foundations/Buttons",
  component: Button,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: { type: "inline-radio" },
      options: ["primary", "secondary", "ghost", "danger"]
    }
  }
};

export default meta;

type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: { children: "Save changes", variant: "primary" }
};

export const Secondary: Story = {
  args: { children: "Cancel", variant: "secondary" }
};

export const Ghost: Story = {
  args: { children: "Manage", variant: "ghost" }
};

export const Danger: Story = {
  args: { children: "Cancel subscription", variant: "danger" }
};

export const WithIcon: Story = {
  args: {
    children: "Open the console",
    variant: "primary",
    icon: <ArrowRight size={16} />
  }
};

export const Group: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      <Button variant="primary" icon={<Plus size={16} />}>
        New plan
      </Button>
      <Button variant="secondary">Import</Button>
      <Button variant="ghost">Cancel</Button>
      <Button variant="danger">Delete</Button>
    </div>
  )
};
