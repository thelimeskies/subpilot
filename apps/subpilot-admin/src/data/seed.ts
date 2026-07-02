// Seed data for the SubPilot admin console. All values are demo-only;
// none of these objects represent live merchant or payment records.

export interface Merchant {
  id: string;
  name: string;
  owner: string;
  ownerEmail: string;
  plan: "Starter" | "Growth" | "Enterprise" | "Internal";
  mrr: string;
  status: "Healthy" | "At risk" | "Suspended";
  failedInvoices: number;
  recoveryRate: string;
  environment: "Live" | "Test";
  createdAt: string;
  region: string;
  monthlyVolume: string;
  activeSubscriptions: number;
}

export const merchants: Merchant[] = [
  {
    id: "mer_acme",
    name: "Acme Learning Hub",
    owner: "Ada Okafor",
    ownerEmail: "ada@acmelearning.co",
    plan: "Growth",
    mrr: "NGN 2.4m",
    status: "Healthy",
    failedInvoices: 4,
    recoveryRate: "92%",
    environment: "Live",
    createdAt: "2025-11-04",
    region: "Lagos, NG",
    monthlyVolume: "NGN 18.6m",
    activeSubscriptions: 1284
  },
  {
    id: "mer_fitplus",
    name: "FitPlus Studio",
    owner: "Tunde Martins",
    ownerEmail: "tunde@fitplus.africa",
    plan: "Starter",
    mrr: "NGN 840k",
    status: "At risk",
    failedInvoices: 18,
    recoveryRate: "61%",
    environment: "Live",
    createdAt: "2026-01-22",
    region: "Abuja, NG",
    monthlyVolume: "NGN 5.2m",
    activeSubscriptions: 412
  },
  {
    id: "mer_creator",
    name: "Creator Desk",
    owner: "Zainab Musa",
    ownerEmail: "zainab@creatordesk.io",
    plan: "Growth",
    mrr: "NGN 1.2m",
    status: "Suspended",
    failedInvoices: 27,
    recoveryRate: "48%",
    environment: "Live",
    createdAt: "2025-08-19",
    region: "Accra, GH",
    monthlyVolume: "NGN 8.1m",
    activeSubscriptions: 605
  },
  {
    id: "mer_kobo",
    name: "Kobo Cloud",
    owner: "Chinedu Bello",
    ownerEmail: "chinedu@kobocloud.app",
    plan: "Enterprise",
    mrr: "NGN 6.9m",
    status: "Healthy",
    failedInvoices: 6,
    recoveryRate: "88%",
    environment: "Live",
    createdAt: "2024-06-12",
    region: "Lagos, NG",
    monthlyVolume: "NGN 41.2m",
    activeSubscriptions: 3210
  },
  {
    id: "mer_savanna",
    name: "Savanna Stream",
    owner: "Kemi Lawal",
    ownerEmail: "kemi@savannastream.tv",
    plan: "Growth",
    mrr: "NGN 1.8m",
    status: "Healthy",
    failedInvoices: 3,
    recoveryRate: "94%",
    environment: "Live",
    createdAt: "2025-04-30",
    region: "Nairobi, KE",
    monthlyVolume: "NGN 12.4m",
    activeSubscriptions: 880
  },
  {
    id: "mer_demo",
    name: "Demo Workspace",
    owner: "SubPilot Team",
    ownerEmail: "demo@subpilot.dev",
    plan: "Internal",
    mrr: "NGN 0",
    status: "Healthy",
    failedInvoices: 2,
    recoveryRate: "100%",
    environment: "Test",
    createdAt: "2026-02-08",
    region: "Lagos, NG",
    monthlyVolume: "NGN 320k",
    activeSubscriptions: 24
  }
];

export interface Payment {
  id: string;
  merchantId: string;
  merchant: string;
  customer: string;
  amount: string;
  status: "Captured" | "Failed" | "Refunded" | "Recovered";
  method: string;
  reason?: string;
  occurredAt: string;
  gateway: "Adapter A" | "Adapter B";
}

export const payments: Payment[] = [
  {
    id: "pay_01HZK8X1",
    merchantId: "mer_acme",
    merchant: "Acme Learning Hub",
    customer: "amaka@acmelearning.co",
    amount: "NGN 15,000",
    status: "Captured",
    method: "Visa 4242",
    occurredAt: "2026-07-05T08:42:11Z",
    gateway: "Adapter A"
  },
  {
    id: "pay_01HZK8X2",
    merchantId: "mer_fitplus",
    merchant: "FitPlus Studio",
    customer: "ifeoma@fitplus.africa",
    amount: "NGN 5,000",
    status: "Failed",
    method: "Mastercard 1881",
    reason: "Insufficient funds",
    occurredAt: "2026-07-05T08:11:54Z",
    gateway: "Adapter A"
  },
  {
    id: "pay_01HZK8X3",
    merchantId: "mer_kobo",
    merchant: "Kobo Cloud",
    customer: "billing@kobocloud.app",
    amount: "NGN 150,000",
    status: "Recovered",
    method: "Visa 2209",
    reason: "Retried after card update",
    occurredAt: "2026-07-04T22:01:09Z",
    gateway: "Adapter B"
  },
  {
    id: "pay_01HZK8X4",
    merchantId: "mer_creator",
    merchant: "Creator Desk",
    customer: "ola@creatordesk.io",
    amount: "NGN 18,500",
    status: "Failed",
    method: "Verve 9911",
    reason: "Token expired",
    occurredAt: "2026-07-04T19:23:42Z",
    gateway: "Adapter B"
  },
  {
    id: "pay_01HZK8X5",
    merchantId: "mer_savanna",
    merchant: "Savanna Stream",
    customer: "fans@savannastream.tv",
    amount: "NGN 4,200",
    status: "Refunded",
    method: "Bank transfer",
    reason: "Duplicate charge",
    occurredAt: "2026-07-04T16:48:01Z",
    gateway: "Adapter A"
  },
  {
    id: "pay_01HZK8X6",
    merchantId: "mer_acme",
    merchant: "Acme Learning Hub",
    customer: "ngozi@acmelearning.co",
    amount: "NGN 15,000",
    status: "Captured",
    method: "Visa 4242",
    occurredAt: "2026-07-04T13:12:22Z",
    gateway: "Adapter A"
  }
];

export interface WebhookDelivery {
  id: string;
  merchant: string;
  event: string;
  endpoint: string;
  status: "Delivered" | "Retrying" | "Failed";
  attempts: number;
  lastAttempt: string;
  responseCode: number;
}

export const webhooks: WebhookDelivery[] = [
  {
    id: "evt_01HZK8YA",
    merchant: "Acme Learning Hub",
    event: "subscription.activated",
    endpoint: "https://api.acmelearning.co/hooks/subpilot",
    status: "Delivered",
    attempts: 1,
    lastAttempt: "2026-07-05T08:42:13Z",
    responseCode: 200
  },
  {
    id: "evt_01HZK8YB",
    merchant: "FitPlus Studio",
    event: "invoice.payment_failed",
    endpoint: "https://hooks.fitplus.africa/subpilot",
    status: "Retrying",
    attempts: 3,
    lastAttempt: "2026-07-05T08:14:42Z",
    responseCode: 503
  },
  {
    id: "evt_01HZK8YC",
    merchant: "Creator Desk",
    event: "subscription.canceled",
    endpoint: "https://creatordesk.io/api/subpilot",
    status: "Failed",
    attempts: 5,
    lastAttempt: "2026-07-04T22:48:09Z",
    responseCode: 500
  },
  {
    id: "evt_01HZK8YD",
    merchant: "Kobo Cloud",
    event: "dunning.recovered",
    endpoint: "https://kobocloud.app/webhooks",
    status: "Delivered",
    attempts: 2,
    lastAttempt: "2026-07-04T22:01:11Z",
    responseCode: 200
  },
  {
    id: "evt_01HZK8YE",
    merchant: "Savanna Stream",
    event: "payment.refunded",
    endpoint: "https://savannastream.tv/svc/subpilot",
    status: "Delivered",
    attempts: 1,
    lastAttempt: "2026-07-04T16:48:03Z",
    responseCode: 200
  }
];

export interface ApiKey {
  id: string;
  label: string;
  prefix: string;
  scope: "Live" | "Test";
  createdBy: string;
  createdAt: string;
  lastUsed: string;
  status: "Active" | "Revoked";
}

export const apiKeys: ApiKey[] = [
  {
    id: "key_01HZ",
    label: "Platform service",
    prefix: "nse_live_42AC...",
    scope: "Live",
    createdBy: "Ada Okafor",
    createdAt: "2025-12-01",
    lastUsed: "2026-07-05T08:42:00Z",
    status: "Active"
  },
  {
    id: "key_02HZ",
    label: "Recovery worker",
    prefix: "nse_live_77BD...",
    scope: "Live",
    createdBy: "Tunde Martins",
    createdAt: "2026-02-15",
    lastUsed: "2026-07-05T07:19:24Z",
    status: "Active"
  },
  {
    id: "key_03HZ",
    label: "Sandbox QA",
    prefix: "nse_test_19FE...",
    scope: "Test",
    createdBy: "Zainab Musa",
    createdAt: "2026-03-22",
    lastUsed: "2026-07-04T14:02:00Z",
    status: "Active"
  },
  {
    id: "key_04HZ",
    label: "Legacy migration",
    prefix: "nse_live_03AA...",
    scope: "Live",
    createdBy: "Ada Okafor",
    createdAt: "2025-04-09",
    lastUsed: "2026-05-22T10:00:00Z",
    status: "Revoked"
  }
];

export interface SupportTicket {
  id: string;
  subject: string;
  merchant: string;
  priority: "Low" | "Normal" | "High" | "Urgent";
  status: "Open" | "Awaiting" | "Resolved";
  assignee: string;
  updatedAt: string;
}

export const tickets: SupportTicket[] = [
  {
    id: "tic_4011",
    subject: "Webhook signature verification rejecting events",
    merchant: "FitPlus Studio",
    priority: "High",
    status: "Open",
    assignee: "Zainab Musa",
    updatedAt: "2026-07-05T07:40:00Z"
  },
  {
    id: "tic_4012",
    subject: "Need to bulk-replay 12 dunning events",
    merchant: "Acme Learning Hub",
    priority: "Normal",
    status: "Awaiting",
    assignee: "Tunde Martins",
    updatedAt: "2026-07-04T19:14:00Z"
  },
  {
    id: "tic_4013",
    subject: "Suspended account appeal",
    merchant: "Creator Desk",
    priority: "Urgent",
    status: "Open",
    assignee: "Ada Okafor",
    updatedAt: "2026-07-04T22:01:00Z"
  },
  {
    id: "tic_4014",
    subject: "Adapter B latency spikes during peak hours",
    merchant: "Kobo Cloud",
    priority: "Normal",
    status: "Resolved",
    assignee: "Tunde Martins",
    updatedAt: "2026-07-03T11:22:00Z"
  }
];

export const platformStats = {
  liveMerchants: 128,
  liveMerchantsDelta: "+14 this month",
  mrr: "NGN 42.8m",
  mrrDelta: "+11.6%",
  revenueAtRisk: "NGN 3.1m",
  revenueAtRiskDelta: "72 failed invoices",
  webhookHealth: "99.2%",
  webhookHealthDelta: "12 retries",
  recoveredThisMonth: "NGN 2.04m",
  recoveryRate: "78.2%"
};

/* ---------- KYC / compliance ------------------------------------- */
export interface KycReview {
  merchantId: string;
  status: "Verified" | "In review" | "Rejected" | "Action needed";
  level: "Tier 1" | "Tier 2" | "Tier 3";
  submittedAt: string;
  reviewedAt?: string;
  reviewer?: string;
  documents: {
    kind: "BVN" | "CAC" | "Director ID" | "Bank statement" | "TIN" | "Utility bill";
    status: "Approved" | "Pending" | "Rejected";
    uploadedAt: string;
    fileName?: string;
    dataUrl?: string;
    url?: string;
  }[];
  flags: string[];
  notes: string;
}

export const kycReviews: Record<string, KycReview> = {
  mer_acme: {
    merchantId: "mer_acme", status: "Verified", level: "Tier 3",
    submittedAt: "2025-11-04", reviewedAt: "2025-11-06", reviewer: "Ada Okafor",
    documents: [
      { kind: "CAC", status: "Approved", uploadedAt: "2025-11-04" },
      { kind: "BVN", status: "Approved", uploadedAt: "2025-11-04" },
      { kind: "Director ID", status: "Approved", uploadedAt: "2025-11-05" },
      { kind: "Bank statement", status: "Approved", uploadedAt: "2025-11-05" },
      { kind: "TIN", status: "Approved", uploadedAt: "2025-11-06" }
    ],
    flags: [], notes: "Clean history. Reviewed by compliance lead."
  },
  mer_fitplus: {
    merchantId: "mer_fitplus", status: "Action needed", level: "Tier 2",
    submittedAt: "2026-01-22", reviewedAt: "2026-01-25", reviewer: "Tunde Martins",
    documents: [
      { kind: "CAC", status: "Approved", uploadedAt: "2026-01-22" },
      { kind: "BVN", status: "Approved", uploadedAt: "2026-01-22" },
      { kind: "Director ID", status: "Pending", uploadedAt: "2026-01-23" },
      { kind: "Utility bill", status: "Rejected", uploadedAt: "2026-01-24" }
    ],
    flags: ["Director ID expired", "Utility bill out of date"],
    notes: "Awaiting refreshed director ID before tier-3 promotion."
  },
  mer_creator: {
    merchantId: "mer_creator", status: "Rejected", level: "Tier 1",
    submittedAt: "2025-08-19", reviewedAt: "2026-06-29", reviewer: "Zainab Musa",
    documents: [
      { kind: "CAC", status: "Approved", uploadedAt: "2025-08-19" },
      { kind: "BVN", status: "Rejected", uploadedAt: "2025-08-19" }
    ],
    flags: ["Sanction list match (manual review)", "Chargeback ratio above 1.2%"],
    notes: "Suspended pending escalation. Owner contacted on 29 Jun."
  },
  mer_kobo: {
    merchantId: "mer_kobo", status: "Verified", level: "Tier 3",
    submittedAt: "2024-06-12", reviewedAt: "2024-06-14", reviewer: "Ada Okafor",
    documents: [
      { kind: "CAC", status: "Approved", uploadedAt: "2024-06-12" },
      { kind: "BVN", status: "Approved", uploadedAt: "2024-06-12" },
      { kind: "Director ID", status: "Approved", uploadedAt: "2024-06-12" },
      { kind: "Bank statement", status: "Approved", uploadedAt: "2024-06-13" },
      { kind: "TIN", status: "Approved", uploadedAt: "2024-06-14" }
    ],
    flags: [], notes: "Enterprise tier — quarterly review on file."
  },
  mer_savanna: {
    merchantId: "mer_savanna", status: "Verified", level: "Tier 2",
    submittedAt: "2025-04-30", reviewedAt: "2025-05-02", reviewer: "Tunde Martins",
    documents: [
      { kind: "CAC", status: "Approved", uploadedAt: "2025-04-30" },
      { kind: "BVN", status: "Approved", uploadedAt: "2025-04-30" },
      { kind: "Bank statement", status: "Approved", uploadedAt: "2025-05-01" }
    ],
    flags: [], notes: "Cross-border (KE) — annual review next April."
  },
  mer_demo: {
    merchantId: "mer_demo", status: "In review", level: "Tier 1",
    submittedAt: "2026-02-08",
    documents: [{ kind: "CAC", status: "Pending", uploadedAt: "2026-02-08" }],
    flags: ["Internal sandbox account"], notes: "Internal — not customer-facing."
  }
};

/* ---------- Audit log -------------------------------------------- */
export interface AuditEntry {
  id: string;
  merchantId?: string;
  actor: string;
  action: string;
  detail: string;
  occurredAt: string;
  category: "merchant" | "platform" | "team" | "security";
}

export const auditLog: AuditEntry[] = [
  { id: "aud_8001", merchantId: "mer_fitplus", actor: "Tunde Martins", action: "KYC reminder sent", detail: "Director ID upload reminder emailed to tunde@fitplus.africa.", occurredAt: "2026-07-05T09:11:00Z", category: "merchant" },
  { id: "aud_8002", merchantId: "mer_creator", actor: "Ada Okafor", action: "Merchant suspended", detail: "Account suspended for chargeback ratio above 1.2%.", occurredAt: "2026-06-29T14:02:00Z", category: "merchant" },
  { id: "aud_8003", merchantId: "mer_acme", actor: "Ada Okafor", action: "Webhook secret rotated", detail: "Endpoint https://api.acmelearning.co/hooks/subpilot signing key rolled.", occurredAt: "2026-06-12T10:14:00Z", category: "merchant" },
  { id: "aud_8004", actor: "Ada Okafor", action: "API key created", detail: "Live API key prefix nse_live_42AC... issued for Platform service.", occurredAt: "2025-12-01T11:00:00Z", category: "platform" },
  { id: "aud_8005", actor: "Zainab Musa", action: "Joined as Support", detail: "Invitation accepted for support@subpilot.dev.", occurredAt: "2025-09-04T08:30:00Z", category: "team" },
  { id: "aud_8006", actor: "Ada Okafor", action: "Adapter A failover", detail: "Auto-routed 14% of charges to Adapter B for 22 minutes.", occurredAt: "2026-07-04T18:42:00Z", category: "platform" },
  { id: "aud_8007", actor: "Tunde Martins", action: "Dunning policy updated", detail: "Default retry cadence changed from 3→4 attempts over 9 days.", occurredAt: "2026-05-18T15:00:00Z", category: "platform" },
  { id: "aud_8008", actor: "system", action: "MFA enforced", detail: "All Owner/Operator accounts now require TOTP.", occurredAt: "2026-04-02T07:00:00Z", category: "security" }
];

/* ---------- Per-merchant limits & config ------------------------- */
export interface MerchantConfig {
  merchantId: string;
  monthlyVolumeCap: string;
  maxTicketSize: string;
  highRiskMcc: boolean;
  payoutCadence: "Daily" | "Weekly" | "T+2";
  notificationChannel: "Email" | "Slack" | "Email + Slack";
  webhookEndpoints: { url: string; events: string[]; status: "Active" | "Disabled" }[];
  retryPolicy: { attempts: number; backoff: "Linear" | "Exponential"; cooldownHours: number };
  features: { tokenizedCards: boolean; manualRefunds: boolean; promoCodes: boolean; smartRouting: boolean };
}

export const merchantConfigs: Record<string, MerchantConfig> = {
  mer_acme: {
    merchantId: "mer_acme", monthlyVolumeCap: "NGN 50m", maxTicketSize: "NGN 250,000",
    highRiskMcc: false, payoutCadence: "Daily", notificationChannel: "Email + Slack",
    webhookEndpoints: [
      { url: "https://api.acmelearning.co/hooks/subpilot", events: ["subscription.*", "invoice.*"], status: "Active" }
    ],
    retryPolicy: { attempts: 4, backoff: "Exponential", cooldownHours: 6 },
    features: { tokenizedCards: true, manualRefunds: true, promoCodes: true, smartRouting: true }
  },
  mer_fitplus: {
    merchantId: "mer_fitplus", monthlyVolumeCap: "NGN 10m", maxTicketSize: "NGN 25,000",
    highRiskMcc: false, payoutCadence: "Weekly", notificationChannel: "Email",
    webhookEndpoints: [
      { url: "https://hooks.fitplus.africa/subpilot", events: ["invoice.*"], status: "Active" }
    ],
    retryPolicy: { attempts: 3, backoff: "Linear", cooldownHours: 4 },
    features: { tokenizedCards: true, manualRefunds: false, promoCodes: false, smartRouting: false }
  },
  mer_creator: {
    merchantId: "mer_creator", monthlyVolumeCap: "NGN 0 (suspended)", maxTicketSize: "NGN 0",
    highRiskMcc: true, payoutCadence: "T+2", notificationChannel: "Email",
    webhookEndpoints: [
      { url: "https://creatordesk.io/api/subpilot", events: ["subscription.*"], status: "Disabled" }
    ],
    retryPolicy: { attempts: 5, backoff: "Exponential", cooldownHours: 12 },
    features: { tokenizedCards: false, manualRefunds: false, promoCodes: false, smartRouting: false }
  },
  mer_kobo: {
    merchantId: "mer_kobo", monthlyVolumeCap: "NGN 200m", maxTicketSize: "NGN 2,000,000",
    highRiskMcc: false, payoutCadence: "Daily", notificationChannel: "Email + Slack",
    webhookEndpoints: [
      { url: "https://kobocloud.app/webhooks", events: ["*"], status: "Active" }
    ],
    retryPolicy: { attempts: 6, backoff: "Exponential", cooldownHours: 8 },
    features: { tokenizedCards: true, manualRefunds: true, promoCodes: true, smartRouting: true }
  },
  mer_savanna: {
    merchantId: "mer_savanna", monthlyVolumeCap: "NGN 30m", maxTicketSize: "NGN 100,000",
    highRiskMcc: false, payoutCadence: "Weekly", notificationChannel: "Email",
    webhookEndpoints: [
      { url: "https://savannastream.tv/svc/subpilot", events: ["payment.*", "subscription.*"], status: "Active" }
    ],
    retryPolicy: { attempts: 4, backoff: "Exponential", cooldownHours: 6 },
    features: { tokenizedCards: true, manualRefunds: true, promoCodes: true, smartRouting: false }
  },
  mer_demo: {
    merchantId: "mer_demo", monthlyVolumeCap: "NGN 1m", maxTicketSize: "NGN 5,000",
    highRiskMcc: false, payoutCadence: "Daily", notificationChannel: "Email",
    webhookEndpoints: [
      { url: "https://demo.subpilot.dev/hooks", events: ["*"], status: "Active" }
    ],
    retryPolicy: { attempts: 3, backoff: "Linear", cooldownHours: 2 },
    features: { tokenizedCards: true, manualRefunds: true, promoCodes: true, smartRouting: true }
  }
};

/* ---------- Per-merchant subscription summary -------------------- */
export interface MerchantSubscriptionStat {
  merchantId: string;
  active: number;
  trialing: number;
  paused: number;
  canceledMtd: number;
  topPlan: string;
  arpu: string;
  churnRate: string;
}

export const merchantSubscriptionStats: Record<string, MerchantSubscriptionStat> = {
  mer_acme: { merchantId: "mer_acme", active: 1284, trialing: 142, paused: 18, canceledMtd: 22, topPlan: "Annual Pro", arpu: "NGN 1,950", churnRate: "1.7%" },
  mer_fitplus: { merchantId: "mer_fitplus", active: 412, trialing: 60, paused: 14, canceledMtd: 18, topPlan: "Monthly Studio", arpu: "NGN 2,100", churnRate: "4.4%" },
  mer_creator: { merchantId: "mer_creator", active: 605, trialing: 0, paused: 605, canceledMtd: 41, topPlan: "Creator Plus", arpu: "NGN 2,000", churnRate: "6.8%" },
  mer_kobo: { merchantId: "mer_kobo", active: 3210, trialing: 280, paused: 22, canceledMtd: 19, topPlan: "Enterprise", arpu: "NGN 2,200", churnRate: "0.8%" },
  mer_savanna: { merchantId: "mer_savanna", active: 880, trialing: 110, paused: 4, canceledMtd: 11, topPlan: "Stream Family", arpu: "NGN 2,050", churnRate: "1.3%" },
  mer_demo: { merchantId: "mer_demo", active: 24, trialing: 6, paused: 0, canceledMtd: 0, topPlan: "Demo plan", arpu: "NGN 0", churnRate: "—" }
};

/* ---------- Admin team ------------------------------------------- */
export interface AdminMember {
  id: string;
  name: string;
  email: string;
  role: "Owner" | "Operator" | "Support" | "Read-only";
  status: "Active" | "Invited" | "Suspended";
  mfa: boolean;
  lastActive: string;
  invitedBy: string;
  initials: string;
}

export const adminMembers: AdminMember[] = [
  { id: "adm_owner", name: "Ada Okafor", email: "owner@subpilot.dev", role: "Owner", status: "Active", mfa: true, lastActive: "2026-07-05T08:11:00Z", invitedBy: "—", initials: "AO" },
  { id: "adm_ops", name: "Tunde Martins", email: "ops@subpilot.dev", role: "Operator", status: "Active", mfa: true, lastActive: "2026-07-05T07:42:00Z", invitedBy: "Ada Okafor", initials: "TM" },
  { id: "adm_support", name: "Zainab Musa", email: "support@subpilot.dev", role: "Support", status: "Active", mfa: true, lastActive: "2026-07-04T19:10:00Z", invitedBy: "Ada Okafor", initials: "ZM" },
  { id: "adm_finance", name: "Chinedu Bello", email: "finance@subpilot.dev", role: "Read-only", status: "Active", mfa: false, lastActive: "2026-07-03T11:00:00Z", invitedBy: "Ada Okafor", initials: "CB" },
  { id: "adm_invite", name: "Kemi Lawal", email: "kemi@subpilot.dev", role: "Operator", status: "Invited", mfa: false, lastActive: "—", invitedBy: "Ada Okafor", initials: "KL" }
];

/* ---------- Platform adapters & policy --------------------------- */
export const adapterStatus = [
  { name: "Adapter A", role: "Primary card processor", uptime: "99.97%", latencyP95: "412 ms", failoverTrigger: "5xx > 4% over 3 minutes", region: "Lagos · Frankfurt", status: "Operational" as const },
  { name: "Adapter B", role: "Backup + bank transfer", uptime: "99.91%", latencyP95: "684 ms", failoverTrigger: "5xx > 6% over 5 minutes", region: "Lagos · Dublin", status: "Monitoring" as const },
  { name: "Tokenization vault", role: "Card tokenization (PCI scope)", uptime: "99.99%", latencyP95: "118 ms", failoverTrigger: "n/a", region: "Lagos · Frankfurt", status: "Operational" as const }
];

export const platformPolicy = {
  defaultRetryAttempts: 4,
  defaultBackoff: "Exponential" as const,
  defaultCooldownHours: 6,
  webhookSignatureHeader: "X-SubPilot-Signature",
  webhookSignatureKeyAge: "Rolled 12 days ago",
  passwordMinLength: 12,
  sessionLifetimeHours: 12,
  ipAllowlistEnabled: false,
  enforcedMfa: true,
  dataRetentionDays: 540
};

/* ---------- Revenue & analytics ---------------------------------- */
export interface RevenuePoint {
  month: string;
  mrr: number;        // in NGN (millions)
  newMrr: number;
  churnMrr: number;
  expansionMrr: number;
  gmv: number;        // gross merchandise volume, NGN millions
  activeSubs: number;
}

export const revenueSeries: RevenuePoint[] = [
  { month: "Aug 25", mrr: 12.4, newMrr: 1.8, churnMrr: 0.4, expansionMrr: 0.3, gmv: 92, activeSubs: 4120 },
  { month: "Sep 25", mrr: 14.0, newMrr: 2.1, churnMrr: 0.5, expansionMrr: 0.4, gmv: 104, activeSubs: 4480 },
  { month: "Oct 25", mrr: 15.6, newMrr: 2.0, churnMrr: 0.5, expansionMrr: 0.5, gmv: 117, activeSubs: 4810 },
  { month: "Nov 25", mrr: 17.2, newMrr: 2.2, churnMrr: 0.6, expansionMrr: 0.6, gmv: 128, activeSubs: 5170 },
  { month: "Dec 25", mrr: 18.9, newMrr: 2.4, churnMrr: 0.7, expansionMrr: 0.7, gmv: 142, activeSubs: 5560 },
  { month: "Jan 26", mrr: 20.7, newMrr: 2.6, churnMrr: 0.8, expansionMrr: 0.9, gmv: 156, activeSubs: 5980 },
  { month: "Feb 26", mrr: 22.1, newMrr: 2.4, churnMrr: 0.9, expansionMrr: 1.0, gmv: 168, activeSubs: 6280 },
  { month: "Mar 26", mrr: 24.0, newMrr: 2.8, churnMrr: 0.9, expansionMrr: 1.1, gmv: 184, activeSubs: 6650 },
  { month: "Apr 26", mrr: 25.6, newMrr: 2.6, churnMrr: 1.0, expansionMrr: 1.0, gmv: 196, activeSubs: 6970 },
  { month: "May 26", mrr: 27.4, newMrr: 2.9, churnMrr: 1.1, expansionMrr: 1.2, gmv: 213, activeSubs: 7340 },
  { month: "Jun 26", mrr: 29.1, newMrr: 2.7, churnMrr: 1.1, expansionMrr: 1.3, gmv: 226, activeSubs: 7660 },
  { month: "Jul 26", mrr: 31.0, newMrr: 3.1, churnMrr: 1.2, expansionMrr: 1.4, gmv: 242, activeSubs: 8010 }
];

export interface PlanRevenueRow {
  plan: string;
  merchants: number;
  activeSubs: number;
  mrr: string;
  share: number;       // 0..1
  arpu: string;
  churn: string;
}
export const planRevenue: PlanRevenueRow[] = [
  { plan: "Enterprise", merchants: 14, activeSubs: 1820, mrr: "NGN 14.6m", share: 0.47, arpu: "NGN 8,021", churn: "1.1%" },
  { plan: "Growth",     merchants: 38, activeSubs: 3640, mrr: "NGN 10.2m", share: 0.33, arpu: "NGN 2,803", churn: "2.4%" },
  { plan: "Starter",    merchants: 71, activeSubs: 2140, mrr: "NGN 4.8m",  share: 0.16, arpu: "NGN 2,243", churn: "3.7%" },
  { plan: "Internal",   merchants: 4,  activeSubs: 410,  mrr: "NGN 1.4m",  share: 0.04, arpu: "NGN 3,415", churn: "0.4%" }
];

export interface RegionRevenueRow {
  region: string;
  mrr: string;
  share: number;
  merchants: number;
  growth: string;
  topAdapter: string;
}
export const regionRevenue: RegionRevenueRow[] = [
  { region: "Nigeria",       mrr: "NGN 22.8m", share: 0.74, merchants: 78, growth: "+8.4%", topAdapter: "Adapter A" },
  { region: "Ghana",         mrr: "NGN 3.6m",  share: 0.12, merchants: 18, growth: "+11.0%", topAdapter: "Adapter A" },
  { region: "Kenya",         mrr: "NGN 2.4m",  share: 0.08, merchants: 14, growth: "+6.2%",  topAdapter: "Adapter B" },
  { region: "South Africa",  mrr: "NGN 1.2m",  share: 0.04, merchants: 9,  growth: "+4.1%",  topAdapter: "Adapter B" },
  { region: "Other",         mrr: "NGN 0.6m",  share: 0.02, merchants: 8,  growth: "+2.0%",  topAdapter: "Adapter A" }
];

export interface CohortRow {
  cohort: string;       // e.g. "Jan 26"
  size: number;         // initial merchants in cohort
  retention: number[];  // retention % per month-since-acquisition (M0..M5), 0..100
}
export const retentionCohorts: CohortRow[] = [
  { cohort: "Feb 26", size: 18, retention: [100, 92, 88, 84, 80, 78] },
  { cohort: "Mar 26", size: 22, retention: [100, 94, 90, 86, 82,  0] },
  { cohort: "Apr 26", size: 19, retention: [100, 91, 86, 82,  0,  0] },
  { cohort: "May 26", size: 24, retention: [100, 93, 89,  0,  0,  0] },
  { cohort: "Jun 26", size: 21, retention: [100, 95,  0,  0,  0,  0] },
  { cohort: "Jul 26", size: 26, retention: [100,  0,  0,  0,  0,  0] }
];

export interface FunnelStep {
  label: string;
  count: number;
  delta?: string;
}
export const acquisitionFunnel: FunnelStep[] = [
  { label: "Signups",            count: 1840, delta: "+12% MoM" },
  { label: "Workspace created",  count: 1462, delta: "79% conv." },
  { label: "First plan added",   count: 1118, delta: "76%" },
  { label: "First payment live", count:  812, delta: "73%" },
  { label: "$1k+ in 30 days",    count:  394, delta: "49%" }
];

export interface PaymentMethodRow {
  method: string;
  share: number;
  successRate: string;
  avgTicket: string;
}
export const paymentMethodMix: PaymentMethodRow[] = [
  { method: "Card",            share: 0.58, successRate: "94.2%", avgTicket: "NGN 8,420" },
  { method: "Bank transfer",   share: 0.27, successRate: "97.6%", avgTicket: "NGN 14,180" },
  { method: "Tokenized card",  share: 0.10, successRate: "96.8%", avgTicket: "NGN 7,950" },
  { method: "USSD",            share: 0.05, successRate: "91.4%", avgTicket: "NGN 4,210" }
];

export const recoveryFunnel = {
  failedThisMonth: 1284,
  recovered: 902,
  pending: 218,
  lost: 164,
  recoveryRate: "70.2%",
  recoveredMrr: "NGN 4.6m",
  byChannel: [
    { channel: "Smart retry",      count: 482, share: 0.53 },
    { channel: "Card update",      count: 228, share: 0.25 },
    { channel: "Customer outreach",count: 144, share: 0.16 },
    { channel: "Bank fallback",    count:  48, share: 0.05 }
  ]
};

export const topMerchantsByRevenue = [
  { id: "mer_acme",     name: "Acme Learning Hub", mrr: "NGN 2.4m", growth: "+8.2%", region: "Lagos, NG" },
  { id: "mer_creator",  name: "Creator Desk",      mrr: "NGN 1.2m", growth: "+5.4%", region: "Abuja, NG" },
  { id: "mer_loop",     name: "Loop Mobility",     mrr: "NGN 1.0m", growth: "+12.1%", region: "Lagos, NG" },
  { id: "mer_fitplus",  name: "FitPlus Studio",    mrr: "NGN 840k", growth: "-2.6%", region: "Abuja, NG" },
  { id: "mer_studio",   name: "Studio Press",      mrr: "NGN 720k", growth: "+3.0%", region: "Accra, GH" }
];
