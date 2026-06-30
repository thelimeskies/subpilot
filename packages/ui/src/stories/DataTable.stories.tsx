import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "../components/Badge";
import { DataTable, type DataTableColumn } from "../components/DataTable";

interface Subscription {
  id: string;
  customer: string;
  plan: string;
  status: "active" | "past_due" | "trialing" | "canceled";
  amount: string;
  nextRenewal: string;
}

const rows: Subscription[] = [
  { id: "sub_001", customer: "Acme Learning Hub", plan: "Growth Monthly", status: "active", amount: "₦24,000", nextRenewal: "Jul 12" },
  { id: "sub_002", customer: "Brightpath Gym", plan: "Pro Annual", status: "past_due", amount: "₦480,000", nextRenewal: "Jun 28" },
  { id: "sub_003", customer: "Coral Salon", plan: "Starter Monthly", status: "trialing", amount: "₦8,000", nextRenewal: "Jul 04" },
  { id: "sub_004", customer: "Delta Tutors", plan: "Growth Monthly", status: "canceled", amount: "₦24,000", nextRenewal: "—" }
];

const tones = {
  active: "success",
  past_due: "warning",
  trialing: "info",
  canceled: "danger"
} as const;

const columns: DataTableColumn<Subscription>[] = [
  { key: "customer", header: "Customer", render: (row) => <strong>{row.customer}</strong> },
  { key: "plan", header: "Plan", render: (row) => row.plan },
  { key: "status", header: "Status", render: (row) => <Badge tone={tones[row.status]}>{row.status.replace("_", " ")}</Badge> },
  { key: "amount", header: "Amount", align: "right", render: (row) => row.amount },
  { key: "next", header: "Next renewal", align: "right", render: (row) => row.nextRenewal }
];

const meta: Meta<typeof DataTable<Subscription>> = {
  title: "Data/DataTable",
  component: DataTable,
  tags: ["autodocs"]
};

export default meta;

type Story = StoryObj<typeof DataTable<Subscription>>;

export const Default: Story = {
  args: {
    columns,
    rows,
    getRowKey: (row) => row.id
  }
};

export const Empty: Story = {
  args: {
    columns,
    rows: [],
    getRowKey: (row) => row.id,
    emptyText: "No subscriptions match your filters."
  }
};
