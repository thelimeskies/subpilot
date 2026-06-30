import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Pause, Play, Trash2 } from "lucide-react";
import { Tabs } from "../components/Tabs";
import { SegmentedControl } from "../components/SegmentedControl";
import { Pagination } from "../components/Pagination";
import { Breadcrumbs } from "../components/PageUtilities";
import { Menu } from "../components/Menu";
import { Tooltip } from "../components/Tooltip";
import { Button } from "../components/Button";

const meta: Meta = {
  title: "Navigation/Controls",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const TabsStory: Story = {
  name: "Tabs",
  render: () => {
    const [value, setValue] = useState("active");
    return (
      <Tabs
        value={value}
        onChange={setValue}
        items={[
          { label: "Active", value: "active", count: 1284 },
          { label: "Trialing", value: "trialing", count: 42 },
          { label: "Past due", value: "past_due", count: 18 },
          { label: "Canceled", value: "canceled", count: 7 }
        ]}
      />
    );
  }
};

export const Segmented: Story = {
  render: () => {
    const [value, setValue] = useState("month");
    return (
      <SegmentedControl
        label="Billing cycle"
        value={value}
        onChange={setValue}
        items={[
          { label: "Monthly", value: "month" },
          { label: "Quarterly", value: "quarter" },
          { label: "Annual", value: "year" }
        ]}
      />
    );
  }
};

export const PaginationStory: Story = {
  name: "Pagination",
  render: () => {
    const [page, setPage] = useState(2);
    return (
      <Pagination
        page={page}
        pageCount={12}
        totalLabel="Showing 21–40 of 234 subscriptions"
        onPageChange={setPage}
      />
    );
  }
};

export const Crumbs: Story = {
  render: () => <Breadcrumbs items={["Subscriptions", "Acme Learning Hub", "Growth Monthly"]} />
};

export const MenuStory: Story = {
  name: "Menu",
  render: () => (
    <Menu
      items={[
        { label: "Pause subscription", icon: <Pause size={16} />, description: "Stops renewals until resumed." },
        { label: "Resume", icon: <Play size={16} />, description: "Resume next billing cycle." },
        { label: "Cancel", icon: <Trash2 size={16} />, destructive: true, description: "End at current period." }
      ]}
    />
  )
};

export const TooltipStory: Story = {
  name: "Tooltip",
  render: () => (
    <div style={{ padding: 32 }}>
      <Tooltip label="Charge will retry automatically every 3 days for up to 21 days.">
        <Button variant="secondary">Smart retry</Button>
      </Tooltip>
    </div>
  )
};
