import type { LucideIcon } from "lucide-react";
import {
  Layers,
  CreditCard,
  ListRestart,
  Receipt,
  Shield,
  Webhook,
  UserRoundCog,
  Activity,
  Building2,
  Users,
  Store,
  GraduationCap,
  Code2
} from "lucide-react";

export interface Pillar {
  icon: LucideIcon;
  title: string;
  body: string;
  proof: string;
}

export const pillars: Pillar[] = [
  {
    icon: Layers,
    title: "Plan catalog and billing cycles",
    body: "Monthly, annual, and custom cycles with trials, setup fees, and usage components, all version-controlled.",
    proof: "draft → published"
  },
  {
    icon: Activity,
    title: "Subscription lifecycle",
    body: "Ten explicit subscription states. Every transition is auditable, idempotent, and reversible where it should be.",
    proof: "incomplete → trialing → active"
  },
  {
    icon: Receipt,
    title: "Invoice and collection",
    body: "Invoices generated on cycle close. Tokenized renewals charge automatically. Refunds and credits are first class.",
    proof: "open → paid"
  },
  {
    icon: ListRestart,
    title: "Dunning and recovery",
    body: "Retry schedules, customer recovery emails, secure update-card sessions, and final-action policy in one builder.",
    proof: "past_due → active"
  },
  {
    icon: CreditCard,
    title: "Tokenized-card primitives",
    body: "SubPilot stores card token references and orchestrates renewals. Raw card data never enters the platform.",
    proof: "token → charge"
  },
  {
    icon: UserRoundCog,
    title: "Customer self-service",
    body: "Embeddable portal sessions for card update, pause, resume, and cancellation with proration preview.",
    proof: "session → resolved"
  },
  {
    icon: Webhook,
    title: "Signed developer webhooks",
    body: "Idempotent events, signature verification, replay tooling, and a delivery log developers can trust.",
    proof: "delivered → acknowledged"
  },
  {
    icon: Shield,
    title: "Operations and audit",
    body: "Multi-tenant isolation, RBAC, environment switcher, and an actor-stamped audit log on every state change.",
    proof: "actor → action → state"
  }
];

export type LifecycleTone = "neutral" | "info" | "success" | "warning" | "danger" | "paused";

export interface LifecycleNode {
  id: string;
  label: string;
  tone: LifecycleTone;
  description: string;
}

export const lifecycleNodes: LifecycleNode[] = [
  { id: "draft", label: "Draft", tone: "neutral", description: "Created internally, not yet started." },
  { id: "incomplete", label: "Incomplete", tone: "info", description: "Checkout or first payment pending." },
  { id: "trialing", label: "Trialing", tone: "info", description: "Trial active, customer has access." },
  { id: "active", label: "Active", tone: "success", description: "Paid and current. Renewals charge automatically." },
  { id: "past_due", label: "Past due", tone: "warning", description: "Payment failed but still recoverable." },
  { id: "paused", label: "Paused", tone: "paused", description: "Subscription paused without cancellation." },
  { id: "unpaid", label: "Unpaid", tone: "danger", description: "Dunning exhausted, customer blocked." },
  { id: "canceling", label: "Canceling", tone: "warning", description: "Will cancel at period end. Access remains." },
  { id: "canceled", label: "Canceled", tone: "neutral", description: "Ended. No further renewals." },
  { id: "expired", label: "Expired", tone: "neutral", description: "Checkout or trial expired before activation." }
];

export interface Segment {
  icon: LucideIcon;
  title: string;
  body: string;
}

export const segments: Segment[] = [
  {
    icon: Building2,
    title: "SaaS companies",
    body: "Trials, upgrades, downgrades, annual plans, and proration without rebuilding subscription logic."
  },
  {
    icon: Users,
    title: "Membership businesses",
    body: "Simple monthly recurring plans with disciplined retry and recovery when cards fail."
  },
  {
    icon: Store,
    title: "Marketplaces and platforms",
    body: "Multi-tenant billing for many merchants or sub-accounts with clean isolation and RBAC."
  },
  {
    icon: GraduationCap,
    title: "Education and creator",
    body: "Customer portals, self-service cancellation, and renewal reminders that protect lifetime value."
  },
  {
    icon: Code2,
    title: "API-first product teams",
    body: "Drop-in subscription engine so product surfaces can stay focused on the core experience."
  }
];

export interface DunningStep {
  day: string;
  label: string;
  detail: string;
  tone: "danger" | "warning" | "info" | "success";
}

export const dunningSteps: DunningStep[] = [
  { day: "Day 0", label: "Renewal failed", detail: "Tokenized charge declined. Subscription moves to past_due.", tone: "danger" },
  { day: "Day 1", label: "First smart retry", detail: "Re-attempt with bank-aware timing. Customer notified by email.", tone: "warning" },
  { day: "Day 3", label: "Second retry", detail: "Re-attempt and surface the issue inside the merchant console.", tone: "warning" },
  { day: "Day 5", label: "Recovery link", detail: "Secure portal session sent so the customer can update their card.", tone: "info" },
  { day: "Day 7", label: "Final action", detail: "Policy decides: cancel, keep unpaid, or pause until update.", tone: "success" }
];

export interface FaqItem {
  question: string;
  answer: string;
}

export const faqs: FaqItem[] = [
  {
    question: "How is SubPilot different from a payment gateway?",
    answer:
      "SubPilot is the subscription operations layer that sits on top of your gateway. It handles plans, lifecycle, proration, dunning, customer self-service, and signed developer webhooks while your gateway handles the underlying card charges and transfers."
  },
  {
    question: "Where do customer cards live?",
    answer:
      "Cards are tokenized by your payment provider at checkout. SubPilot stores the token reference, never raw card data, and uses it to orchestrate renewals through the charge API."
  },
  {
    question: "Can I migrate from a custom billing setup?",
    answer:
      "Yes. Plans, customers, subscriptions, and tokens can be imported. Webhooks for existing systems can stay live during cutover thanks to idempotency keys and replay tooling."
  },
  {
    question: "How does dunning work in practice?",
    answer:
      "Failed renewals enter past_due. A retry schedule, customer recovery email, and update-card portal session run automatically. Final action is policy-driven: cancel, keep unpaid, or pause."
  },
  {
    question: "Do you support multi-tenant operators?",
    answer:
      "Yes. Merchants, environments, and sub-accounts are first-class. Test and Live are isolated. RBAC controls who can preview proration, refund, retry, or replay webhooks."
  },
  {
    question: "What about annual and custom cycles?",
    answer:
      "Monthly, annual, and custom cycles are supported, including mid-cycle changes with proration preview before confirmation."
  }
];

export const codeSamples = {
  python: `from subpilot import SubPilot

client = SubPilot(api_key=os.environ["SUBPILOT_KEY"])

customer = client.customers.create(
    email="ada@example.com",
    name="Ada Okafor",
    external_id="user_123",
)

session = client.portal_sessions.create(
    customer_id=customer["id"],
    allowed_actions=["view_invoices", "update_payment_method"],
    ttl_minutes=60,
)

return {"portal_token": session["token"]}`,
  node: `import { SubPilot } from "@subpilot/node";

const client = new SubPilot({ apiKey: process.env.SUBPILOT_KEY });

const subscription = await client.subscriptions.create({
  customer: { email: "ada@example.com" },
  items: [{ plan_id: "plan_pro_monthly" }],
  idempotencyKey: "sub-user-123-pro",
});

res.redirect(subscription.checkout_url);`,
  curl: `curl -X POST https://api.subpilot.kylodo.com/api/v1/subscriptions \\
  -H "Authorization: Bearer $SUBPILOT_KEY" \\
  -H "Idempotency-Key: sub-user-123-pro" \\
  -H "Content-Type: application/json" \\
  -d '{
    "customer": { "email": "ada@example.com" },
    "items": [{ "plan_id": "plan_pro_monthly" }]
  }'`
};

export const webhookEvent = `{
  "id": "evt_01HZK4YQX2",
  "type": "subscription.activated",
  "created": "2026-07-05T10:14:22Z",
  "idempotency_key": "sub-user-123-pro",
  "data": {
    "subscription_id": "sub_01HZK4Y8Q",
    "customer_id": "cus_01HZK4YA1",
    "plan_id": "plan_pro_monthly",
    "status": "active",
    "current_period_end": "2026-07-19T10:14:22Z"
  },
  "signature": "t=1718793262,v1=4f0c9b…"
}`;

export const trustChips = [
  "Plans",
  "Tokenized renewals",
  "Proration",
  "Dunning",
  "Customer portal",
  "Signed webhooks",
  "Multi-tenant",
  "Audit log"
];
