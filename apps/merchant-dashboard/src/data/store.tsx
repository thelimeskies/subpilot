// In-memory mutable layer over the seed data. Provides every CRUD-ish
// operation the rest of the merchant dashboard needs (create plan, void
// invoice, refund payment, rotate API key, etc.) backed by `useState` —
// not by mutating the seed export. Future swap to a real backend = replace
// this file only; the React API surface stays the same.
//
// Conventions:
//   - Mutations return `void` (or the new entity id where the caller needs
//     it for navigation). They never throw on missing ids — the store is a
//     UI fixture and the UI is responsible for only firing valid actions.
//   - All array setters call into immutable update helpers so React picks up
//     the change (`createIndex` in `selectors.ts` rebuilds on reference).

import {
  createContext,
  useCallback,
  useEffect,
  useContext,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { useLocation } from "react-router-dom";
import {
  cancelBillingSubscription,
  changeBillingSubscriptionPlan,
  applyBillingInvoiceCredit,
  archiveBillingCustomer,
  attachBillingPaymentMethod,
  createBillingCustomer,
  createBillingInvoice,
  createBillingSubscription,
  downloadBillingInvoicePdf,
  downloadPaymentReceiptPdf,
  exportBillingInvoicesCsv,
  exportPaymentAttemptsCsv,
  markBillingInvoicePaid,
  mergeBillingCustomer,
  pauseBillingSubscription,
  reactivateBillingCustomer,
  refundBillingPayment,
  resumeBillingSubscription,
  setDefaultBillingPaymentMethod,
  updateBillingSubscriptionPaymentMethod,
  sendBillingInvoiceReminder,
  updateBillingCustomer,
  voidBillingInvoice
} from "../api/billing";
import type { ArchivedCustomerResult } from "../api/billing";
import { createBackendApiKey, revokeBackendApiKey } from "../api/apiKeys";
import {
  inviteBackendTeamMember,
  removeBackendTeamMember,
  resendBackendTeamInvite,
  resetBackendTeamMemberMfa,
  updateBackendTeamMemberRole
} from "../api/team";
import { updateWorkspaceDunning, updateWorkspaceOrg, updateWorkspaceSettings } from "../api/settings";
import { addSubscriptionNote, applySubscriptionCredit as applyBackendSubscriptionCredit } from "../api/subscriptions";
import {
  createBackendWebhookEndpoint,
  cancelDunningRun,
  markInvoiceUncollectible,
  pauseDunningRun,
  removeBackendWebhookEndpoint,
  replayBackendWebhookEvent,
  resumeDunningRun,
  retryInvoicePayment,
  rotateBackendWebhookSecret,
  updateBackendWebhookEndpoint
} from "../api/integrations";
import {
  archiveCatalogPlan,
  createCatalogPlan,
  duplicateCatalogPlan,
  updateCatalogPlan
} from "../api/catalog";
import { loadMerchantResourcesForPath, type MerchantResourcePatch } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import {
  apiKeys as seedApiKeys,
  auditEvents as seedAuditEvents,
  customers as seedCustomers,
  defaultSettings,
  invoices as seedInvoices,
  org as seedOrg,
  payments as seedPayments,
  plans as seedPlans,
  recoveryItems as seedRecoveryItems,
  subscriptions as seedSubscriptions,
  teamMembers as seedTeamMembers,
  webhookEndpoints as seedWebhookEndpoints,
  webhookEvents as seedWebhookEvents,
  type ApiKey,
  type AuditEvent,
  type Customer,
  type Invoice,
  type InvoiceStatus,
  type MerchantOrg,
  type MerchantSettings,
  type PaymentChannel,
  type PaymentMethod,
  type PaymentRecord,
  type PaymentRecordStatus,
  type Plan,
  type RecoveryItem,
  type Subscription,
  type TeamMember,
  type WebhookEndpoint,
  type WebhookEventRecord
} from "./seed";

// ---------- Snapshot type ----------

export interface DataSnapshot {
  resourcesLoading: boolean;
  org: MerchantOrg;
  plans: Plan[];
  customers: Customer[];
  subscriptions: Subscription[];
  invoices: Invoice[];
  payments: PaymentRecord[];
  recoveryItems: RecoveryItem[];
  webhookEndpoints: WebhookEndpoint[];
  webhookEvents: WebhookEventRecord[];
  apiKeys: ApiKey[];
  teamMembers: TeamMember[];
  auditEvents: AuditEvent[];
  settings: MerchantSettings;
}

// ---------- Mutation surface ----------

export interface DataActions {
  // Plans
  createPlan: (input: Omit<Plan, "id" | "subscribers" | "createdAt"> & Partial<Pick<Plan, "subscribers">>) => Promise<string>;
  updatePlan: (id: string, patch: Partial<Plan>) => Promise<void>;
  archivePlan: (id: string) => Promise<void>;
  duplicatePlan: (id: string) => Promise<string | null>;

  // Subscriptions
  createSubscription: (input: Omit<Subscription, "id">) => Promise<string>;
  updateSubscription: (id: string, patch: Partial<Subscription>) => Promise<void>;
  cancelSubscription: (id: string, mode: "immediate" | "end_of_period") => Promise<void>;
  pauseSubscription: (id: string, resumeAt: string | null, reason?: string) => Promise<void>;
  resumeSubscription: (id: string) => Promise<void>;
  applySubscriptionCredit: (id: string, amount: number, note?: string) => Promise<void>;

  // Invoices
  createInvoice: (input: Omit<Invoice, "id">) => Promise<string>;
  updateInvoice: (id: string, patch: Partial<Invoice>) => void;
  voidInvoice: (id: string) => Promise<void>;
  markInvoicePaid: (id: string, amount: number) => Promise<void>;
  applyInvoiceCredit: (id: string, amount: number, note?: string) => Promise<void>;
  sendInvoiceReminder: (id: string, channel: "email" | "sms", message: string) => Promise<void>;
  downloadInvoicePdf: (id: string, invoiceNumber: string) => Promise<void>;
  exportInvoicesCsv: (filters?: { status?: InvoiceStatus | "all"; q?: string }) => Promise<void>;

  // Payments
  refundPayment: (id: string, amount: number, full: boolean, reason?: string) => Promise<void>;
  retryPayment: (id: string, paymentMethodId?: string) => Promise<void>;
  retryInvoice: (id: string, paymentMethodId?: string) => Promise<void>;
  downloadPaymentReceipt: (id: string) => Promise<void>;
  exportPaymentsCsv: (filters?: { status?: PaymentRecordStatus | "all"; channel?: PaymentChannel | "all"; q?: string }) => Promise<void>;

  // Customers
  createCustomer: (input: Omit<Customer, "id" | "paymentMethods" | "defaultMethodId" | "mrr" | "createdAt" | "lastPaymentAt"> & Partial<Pick<Customer, "paymentMethods" | "mrr" | "notes">>) => Promise<string>;
  updateCustomer: (id: string, patch: Partial<Customer>) => Promise<void>;
  blockCustomer: (id: string) => Promise<ArchivedCustomerResult>;
  mergeCustomer: (sourceId: string, targetId: string) => Promise<void>;
  addCustomerPaymentMethod: (customerId: string, input: Pick<PaymentMethod, "brand" | "last4" | "expiry">) => Promise<void>;
  setCustomerDefaultPaymentMethod: (id: string) => Promise<void>;

  // Recovery
  resolveRecoveryItem: (
    id: string,
    outcome: "retried" | "skipped" | "uncollectible" | "paused" | "resumed",
    note?: string,
    options?: { pausedUntil?: string }
  ) => Promise<void>;

  // Webhooks
  createWebhookEndpoint: (input: Omit<WebhookEndpoint, "id" | "createdAt" | "lastDeliveryAt" | "successRate">) => Promise<{ id: string; secret: string | null }>;
  updateWebhookEndpoint: (id: string, patch: Partial<WebhookEndpoint>) => Promise<void>;
  removeWebhookEndpoint: (id: string) => Promise<void>;
  rotateWebhookEndpointSecret: (id: string) => Promise<string>;
  replayWebhookEvent: (id: string) => Promise<void>;

  // API keys
  generateApiKey: (input: Omit<ApiKey, "id" | "createdAt" | "lastUsedAt" | "status" | "prefix"> & { mode?: "live" | "test" }) => Promise<{ id: string; secret: string }>;
  revokeApiKey: (id: string) => Promise<void>;

  // Team
  inviteTeamMember: (input: Omit<TeamMember, "id" | "lastSeenAt" | "status" | "mfaEnabled"> & Partial<Pick<TeamMember, "mfaEnabled">> & { message?: string }) => Promise<string>;
  updateTeamMember: (id: string, patch: Partial<TeamMember>) => Promise<void>;
  resendTeamInvite: (id: string) => Promise<void>;
  resetTeamMemberMfa: (id: string) => Promise<void>;
  removeTeamMember: (id: string) => Promise<void>;

  // Settings
  updateSettings: (patch: Partial<MerchantSettings>) => Promise<void>;
  updateOrg: (patch: Partial<MerchantOrg>) => Promise<void>;
  updateDunningSettings: (dunning: MerchantSettings["dunning"]) => Promise<void>;
  refreshResources: () => Promise<void>;

  // Audit log (callers that mutate state can append a record for traceability)
  logAuditEvent: (input: Omit<AuditEvent, "id" | "occurredAt" | "ipAddress"> & Partial<Pick<AuditEvent, "ipAddress">>) => void;
}

export type DataContextValue = DataSnapshot & DataActions;

const DataContext = createContext<DataContextValue | null>(null);

// ---------- Provider ----------

function clone<T>(v: T): T {
  // Plain JSON clone is sufficient for our seed shape.
  return JSON.parse(JSON.stringify(v)) as T;
}

let idCounter = 1_000;
function nextId(prefix: string) {
  idCounter += 1;
  return `${prefix}_${idCounter.toString(16)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function mergeSettings(current: MerchantSettings, incoming: MerchantSettings): MerchantSettings {
  return {
    ...current,
    ...incoming,
    branding: { ...current.branding, ...incoming.branding },
    payouts: { ...current.payouts, ...incoming.payouts },
    planDefaults: { ...current.planDefaults, ...incoming.planDefaults },
    dunning: { ...current.dunning, ...incoming.dunning },
    dunningTemplates: incoming.dunningTemplates ?? current.dunningTemplates,
    notifications: { ...current.notifications, ...incoming.notifications },
    security: { ...current.security, ...incoming.security },
    portal: { ...current.portal, ...incoming.portal }
  };
}

export function DataProvider({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  // The merchant org is rarely mutated, but Settings → Organization edits it,
  // so we still hold it in state.
  const [org, setOrg] = useState<MerchantOrg>(() => clone(seedOrg));
  const [plans, setPlans] = useState<Plan[]>(() => clone(seedPlans));
  const [customers, setCustomers] = useState<Customer[]>(() => clone(seedCustomers));
  const [subscriptions, setSubscriptions] = useState<Subscription[]>(() => clone(seedSubscriptions));
  const [invoices, setInvoices] = useState<Invoice[]>(() => clone(seedInvoices));
  const [payments, setPayments] = useState<PaymentRecord[]>(() => clone(seedPayments));
  const [recoveryItems, setRecoveryItems] = useState<RecoveryItem[]>(() => clone(seedRecoveryItems));
  const [webhookEndpoints, setWebhookEndpoints] = useState<WebhookEndpoint[]>(() => clone(seedWebhookEndpoints));
  const [webhookEvents, setWebhookEvents] = useState<WebhookEventRecord[]>(() => clone(seedWebhookEvents));
  const [apiKeys, setApiKeys] = useState<ApiKey[]>(() => clone(seedApiKeys));
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>(() => clone(seedTeamMembers));
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>(() => clone(seedAuditEvents));
  const [settings, setSettings] = useState<MerchantSettings>(() => clone(defaultSettings));
  const [resourcesLoading, setResourcesLoading] = useState(true);

  const applyResourcePatch = useCallback((resources: MerchantResourcePatch) => {
    if (resources.org) setOrg(resources.org);
    if (resources.settings) setSettings((prev) => mergeSettings(prev, resources.settings!));
    if (resources.plans) setPlans(resources.plans);
    if (resources.subscriptions) setSubscriptions(resources.subscriptions);
    if (resources.invoices) setInvoices(resources.invoices);
    if (resources.customers) setCustomers(resources.customers);
    if (resources.payments) setPayments(resources.payments);
    if (resources.recoveryItems) setRecoveryItems(resources.recoveryItems);
    if (resources.webhookEndpoints) setWebhookEndpoints(resources.webhookEndpoints);
    if (resources.webhookEvents) setWebhookEvents(resources.webhookEvents);
    if (resources.apiKeys) setApiKeys(resources.apiKeys);
    if (resources.teamMembers) setTeamMembers(resources.teamMembers);
    if (resources.auditEvents) setAuditEvents(resources.auditEvents);
  }, []);

  const refreshResources = useCallback(async () => {
    const resources = await loadMerchantResourcesForPath(location.pathname);
    applyResourcePatch(resources);
  }, [applyResourcePatch, location.pathname]);

  useEffect(() => {
    if (status === "loading") return;

    let cancelled = false;

    if (status !== "authenticated") {
      setResourcesLoading(false);
      setPlans(clone(seedPlans));
      setCustomers(clone(seedCustomers));
      setSubscriptions(clone(seedSubscriptions));
      setInvoices(clone(seedInvoices));
      setPayments(clone(seedPayments));
      setRecoveryItems(clone(seedRecoveryItems));
      setWebhookEndpoints(clone(seedWebhookEndpoints));
      setWebhookEvents(clone(seedWebhookEvents));
      setApiKeys(clone(seedApiKeys));
      setTeamMembers(clone(seedTeamMembers));
      setAuditEvents(clone(seedAuditEvents));
      setOrg(clone(seedOrg));
      setSettings(clone(defaultSettings));
      return;
    }

    (async () => {
      setResourcesLoading(true);
      try {
        const resources = await loadMerchantResourcesForPath(location.pathname);
        if (cancelled) return;
        applyResourcePatch(resources);
      } catch (err) {
        if (!cancelled) console.warn("Could not load merchant resources", err);
      } finally {
        if (!cancelled) setResourcesLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [applyResourcePatch, location.pathname, status, user?.id]);

  const value = useMemo<DataContextValue>(() => {
    const logAuditEvent: DataActions["logAuditEvent"] = (input) => {
      setAuditEvents((prev) => [
        {
          id: nextId("aud"),
          occurredAt: nowIso(),
          ipAddress: input.ipAddress ?? "127.0.0.1",
          actor: input.actor,
          action: input.action,
          target: input.target
        },
        ...prev
      ]);
    };

    return {
      org,
      plans,
      customers,
      subscriptions,
      invoices,
      payments,
      recoveryItems,
      webhookEndpoints,
      webhookEvents,
      apiKeys,
      teamMembers,
      auditEvents,
      settings,
      resourcesLoading,

      // ----- Plans -----
      async createPlan(input) {
        const id = await createCatalogPlan(input);
        await refreshResources();
        return id;
      },
      async updatePlan(id, patch) {
        await updateCatalogPlan(id, patch);
        await refreshResources();
      },
      async archivePlan(id) {
        await archiveCatalogPlan(id);
        await refreshResources();
      },
      async duplicatePlan(id) {
        const source = plans.find((p) => p.id === id);
        if (!source) return null;
        const newId = await duplicateCatalogPlan(id, source.name);
        await refreshResources();
        return newId;
      },

      // ----- Subscriptions -----
      async createSubscription(input) {
        const id = await createBillingSubscription(input);
        await refreshResources();
        return id;
      },
      async updateSubscription(id, patch) {
        if (patch.planId) {
          await changeBillingSubscriptionPlan(id, patch.planId);
          await refreshResources();
          return;
        }
        if (patch.paymentMethodId) {
          await updateBillingSubscriptionPaymentMethod(id, patch.paymentMethodId);
          await refreshResources();
          return;
        }
        if (patch.notes !== undefined) {
          await addSubscriptionNote(id, patch.notes);
          await refreshResources();
          return;
        }
        setSubscriptions((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
      },
      async cancelSubscription(id, mode) {
        await cancelBillingSubscription(id, mode, "Cancelled from merchant dashboard");
        await refreshResources();
      },
      async pauseSubscription(id, resumeAt, reason) {
        await pauseBillingSubscription(
          id,
          reason?.trim() || "Paused from merchant dashboard",
          resumeAt
        );
        await refreshResources();
      },
      async resumeSubscription(id) {
        await resumeBillingSubscription(id);
        await refreshResources();
      },
      async applySubscriptionCredit(id, amount, note) {
        await applyBackendSubscriptionCredit(id, amount, note ?? "Applied from merchant dashboard");
        await refreshResources();
      },

      // ----- Invoices -----
      async createInvoice(input) {
        const id = await createBillingInvoice(input);
        await refreshResources();
        return id;
      },
      updateInvoice(id, patch) {
        setInvoices((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)));
      },
      async voidInvoice(id) {
        await voidBillingInvoice(id);
        await refreshResources();
      },
      async markInvoicePaid(id, amount) {
        await markBillingInvoicePaid(id, amount);
        await refreshResources();
      },
      async applyInvoiceCredit(id, amount, note) {
        await applyBillingInvoiceCredit(id, amount, note);
        await refreshResources();
      },
      async sendInvoiceReminder(id, channel, message) {
        await sendBillingInvoiceReminder(id, channel, message);
      },
      async downloadInvoicePdf(id, invoiceNumber) {
        await downloadBillingInvoicePdf(id, invoiceNumber);
      },
      async exportInvoicesCsv(filters) {
        await exportBillingInvoicesCsv(filters);
      },

      // ----- Payments -----
      async refundPayment(id, amount, full, reason) {
        await refundBillingPayment(id, amount, full, reason);
        await refreshResources();
      },
      async retryPayment(id, paymentMethodId) {
        const payment = payments.find((p) => p.id === id);
        if (!payment?.invoiceId) {
          throw new Error("Payment attempt is not linked to an invoice.");
        }
        await retryInvoicePayment(payment.invoiceId, paymentMethodId);
        await refreshResources();
      },
      async retryInvoice(id, paymentMethodId) {
        await retryInvoicePayment(id, paymentMethodId);
        await refreshResources();
      },
      async downloadPaymentReceipt(id) {
        await downloadPaymentReceiptPdf(id);
      },
      async exportPaymentsCsv(filters) {
        await exportPaymentAttemptsCsv(filters);
      },

      // ----- Customers -----
      async createCustomer(input) {
        const id = await createBillingCustomer(input);
        await refreshResources();
        return id;
      },
      async updateCustomer(id, patch) {
        const backendFields: Array<keyof Customer> = ["name", "email", "phone", "country", "notes", "status"];
        const shouldPersist = backendFields.some((field) => patch[field] !== undefined);
        if (shouldPersist) {
          if (patch.status === "blocked") {
            await archiveBillingCustomer(id);
          } else if (patch.status === "active") {
            await reactivateBillingCustomer(id);
          }
          await updateBillingCustomer(id, patch);
          await refreshResources();
          return;
        }
        setCustomers((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
      },
      async blockCustomer(id) {
        const result = await archiveBillingCustomer(id);
        await refreshResources();
        return result;
      },
      async mergeCustomer(sourceId, targetId) {
        await mergeBillingCustomer(sourceId, targetId);
        await refreshResources();
      },
      async addCustomerPaymentMethod(customerId, input) {
        const customer = customers.find((c) => c.id === customerId);
        await attachBillingPaymentMethod(customerId, {
          ...input,
          setDefault: (customer?.paymentMethods.length ?? 0) === 0
        });
        await refreshResources();
      },
      async setCustomerDefaultPaymentMethod(id) {
        await setDefaultBillingPaymentMethod(id);
        await refreshResources();
      },

      // ----- Recovery -----
      async resolveRecoveryItem(id, outcome, note, options) {
        const item = recoveryItems.find((r) => r.id === id);
        if (outcome === "retried") {
          if (!item) throw new Error("Recovery item not found.");
          await retryInvoicePayment(item.invoiceId);
          await refreshResources();
          return;
        }
        if (outcome === "uncollectible") {
          if (!item) throw new Error("Recovery item not found.");
          await markInvoiceUncollectible(item.invoiceId);
          await refreshResources();
          return;
        }
        if (outcome === "skipped") {
          if (!item) throw new Error("Recovery item not found.");
          if (!id.startsWith("rec_")) {
            await cancelDunningRun(id, note ?? "Skipped from merchant recovery cockpit");
            await refreshResources();
            return;
          }
        }
        if (outcome === "paused") {
          if (!item) throw new Error("Recovery item not found.");
          if (!id.startsWith("rec_")) {
            await pauseDunningRun(id, note ?? "Paused from merchant recovery cockpit", options?.pausedUntil);
            await refreshResources();
            return;
          }
        }
        if (outcome === "resumed") {
          if (!item) throw new Error("Recovery item not found.");
          if (!id.startsWith("rec_")) {
            await resumeDunningRun(id);
            await refreshResources();
            return;
          }
        }
        setRecoveryItems((prev) =>
          outcome === "paused"
            ? prev.map((r) => (r.id === id ? { ...r, stage: "paused", nextRetryAt: null } : r))
            : prev.filter((r) => r.id !== id)
        );
      },

      // ----- Webhooks -----
      async createWebhookEndpoint(input) {
        const result = await createBackendWebhookEndpoint(input);
        await refreshResources();
        return result;
      },
      async updateWebhookEndpoint(id, patch) {
        await updateBackendWebhookEndpoint(id, patch);
        await refreshResources();
      },
      async removeWebhookEndpoint(id) {
        await removeBackendWebhookEndpoint(id);
        await refreshResources();
      },
      async rotateWebhookEndpointSecret(id) {
        const secret = await rotateBackendWebhookSecret(id);
        await refreshResources();
        return secret;
      },
      async replayWebhookEvent(id) {
        await replayBackendWebhookEvent(id);
        await refreshResources();
      },

      // ----- API keys -----
      async generateApiKey(input) {
        const result = await createBackendApiKey({
          name: input.name,
          scopes: input.scopes,
          mode: input.mode ?? "test"
        });
        await refreshResources();
        return result;
      },
      async revokeApiKey(id) {
        await revokeBackendApiKey(id);
        await refreshResources();
      },

      // ----- Team -----
      async inviteTeamMember(input) {
        const id = await inviteBackendTeamMember({
          email: input.email,
          name: input.name,
          role: input.role,
          message: input.message
        });
        await refreshResources();
        return id;
      },
      async updateTeamMember(id, patch) {
        if (patch.role) {
          await updateBackendTeamMemberRole(id, patch.role);
          await refreshResources();
          return;
        }
        if (patch.mfaEnabled === false) {
          await resetBackendTeamMemberMfa(id);
          await refreshResources();
          return;
        }
      },
      async resendTeamInvite(id) {
        await resendBackendTeamInvite(id);
        await refreshResources();
      },
      async resetTeamMemberMfa(id) {
        await resetBackendTeamMemberMfa(id);
        await refreshResources();
      },
      async removeTeamMember(id) {
        await removeBackendTeamMember(id);
        await refreshResources();
      },

      // ----- Settings -----
      async updateSettings(patch) {
        const resources = await updateWorkspaceSettings(patch);
        setOrg(resources.org);
        setSettings((prev) => mergeSettings(prev, resources.settings));
      },
      async updateOrg(patch) {
        const resources = await updateWorkspaceOrg(patch);
        setOrg(resources.org);
        setSettings((prev) => mergeSettings(prev, resources.settings));
      },
      async updateDunningSettings(dunning) {
        const resources = await updateWorkspaceDunning(dunning);
        setOrg(resources.org);
        setSettings((prev) => mergeSettings(prev, resources.settings));
      },
      refreshResources,

      // ----- Audit -----
      logAuditEvent
    };
  }, [
    org,
    plans,
    customers,
    subscriptions,
    invoices,
    payments,
    recoveryItems,
    webhookEndpoints,
    webhookEvents,
    apiKeys,
    teamMembers,
    auditEvents,
    settings,
    resourcesLoading,
    refreshResources
  ]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

// ---------- Hook ----------

export function useData(): DataContextValue {
  const ctx = useContext(DataContext);
  if (!ctx) {
    throw new Error("useData must be used within <DataProvider/>");
  }
  return ctx;
}

export function useOptionalData(): DataContextValue | null {
  return useContext(DataContext);
}
