import type { Meta, StoryObj } from "@storybook/react";
import { Plus } from "lucide-react";
import { Button } from "../components/Button";
import { FilterBar } from "../components/FilterBar";

const meta: Meta<typeof FilterBar> = {
  title: "Data/Filters",
  component: FilterBar,
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj<typeof FilterBar>;

export const Default: Story = {
  args: {
    searchPlaceholder: "Search customers, plans, IDs",
    filters: [
      {
        label: "Status",
        options: [
          { label: "Active", value: "active" },
          { label: "Trialing", value: "trialing" },
          { label: "Past due", value: "past_due" },
          { label: "Canceled", value: "canceled" }
        ]
      },
      {
        label: "Plan",
        options: [
          { label: "Starter Monthly", value: "starter" },
          { label: "Growth Monthly", value: "growth" },
          { label: "Pro Annual", value: "pro" }
        ]
      }
    ]
  }
};

export const WithAction: Story = {
  args: {
    ...Default.args,
    action: (
      <Button icon={<Plus size={16} />}>New subscription</Button>
    )
  }
};
