import type { Meta, StoryObj } from "@storybook/react";
import { Skeleton, SkeletonTable } from "../components/Skeleton";
import { Timeline } from "../components/PageUtilities";

const meta: Meta = {
  title: "Feedback/Loading and Timeline",
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj;

export const SkeletonBlocks: Story = {
  render: () => (
    <div style={{ display: "grid", gap: 12, maxWidth: 480 }}>
      <Skeleton style={{ height: 24, width: "60%" }} />
      <Skeleton style={{ height: 16 }} />
      <Skeleton style={{ height: 16, width: "80%" }} />
      <Skeleton style={{ height: 16, width: "40%" }} />
    </div>
  )
};

export const TableSkeleton: Story = {
  render: () => <SkeletonTable rows={5} />
};

export const ActivityTimeline: Story = {
  render: () => (
    <Timeline
      items={[
        {
          title: "Subscription created",
          meta: "Jun 12 · 09:14",
          body: "Acme Learning Hub started Growth Monthly with a 7-day trial."
        },
        {
          title: "Trial converted",
          meta: "Jun 19 · 09:14",
          body: "Charged ₦24,000 to tok_4f9. Receipt emailed."
        },
        {
          title: "Card declined",
          meta: "Jul 12 · 09:14",
          body: "Insufficient funds. Smart retry scheduled in 24 hours."
        },
        {
          title: "Recovered",
          meta: "Jul 13 · 09:18",
          body: "Retry succeeded. Subscription back to active."
        }
      ]}
    />
  )
};
