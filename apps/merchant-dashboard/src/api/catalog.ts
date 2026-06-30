import { api } from "./client";
import type { Plan, PlanInterval } from "../data/seed";

interface ProductDto {
  id: string;
  name: string;
}

interface PlanDto {
  id: string;
}

type ListResponse<T> = T[] | { results?: T[] };

const DEFAULT_PRODUCT_NAME = "Merchant subscription catalog";

function asList<T>(body: ListResponse<T>): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

function intervalUnit(interval: PlanInterval): "month" | "year" | "week" {
  if (interval === "yearly") return "year";
  if (interval === "weekly") return "week";
  return "month";
}

async function ensureProduct(): Promise<ProductDto> {
  const products = asList(await api.get<ListResponse<ProductDto>>("/catalog/products/"));
  const existing = products.find((product) => product.name === DEFAULT_PRODUCT_NAME) ?? products[0];
  if (existing) return existing;

  return api.post<ProductDto>("/catalog/products/", {
    name: DEFAULT_PRODUCT_NAME,
    description: "Default product grouping for merchant-created subscription plans.",
    metadata: { source: "merchant_dashboard" }
  });
}

async function createPriceVersion(planId: string, plan: Pick<Plan, "amount" | "currency" | "interval">) {
  return api.post(`/catalog/plans/${planId}/price-versions/`, {
    amount_minor: Math.round(plan.amount * 100),
    currency: plan.currency,
    interval_unit: intervalUnit(plan.interval),
    interval_count: 1,
    setup_fee_minor: 0
  });
}

export async function createCatalogPlan(
  input: Omit<Plan, "id" | "subscribers" | "createdAt"> & Partial<Pick<Plan, "subscribers">>
): Promise<string> {
  const product = await ensureProduct();
  const plan = await api.post<PlanDto>("/catalog/plans/", {
    product_id: product.id,
    name: input.name,
    description: input.description,
    trial_days: input.trialDays,
    proration_policy: "prorate",
    cancellation_policy: "at_period_end",
    tokenized_renewal: true,
    metadata: { code: input.code }
  });

  await createPriceVersion(plan.id, input);
  if (input.status === "active") {
    await api.post(`/catalog/plans/${plan.id}/activate/`);
  } else if (input.status === "archived") {
    await api.post(`/catalog/plans/${plan.id}/archive/`);
  }

  return plan.id;
}

export async function updateCatalogPlan(id: string, patch: Partial<Plan>): Promise<void> {
  const metadata = patch.code ? { code: patch.code } : undefined;
  const planPatch: Record<string, unknown> = {};
  if (patch.name !== undefined) planPatch.name = patch.name;
  if (patch.description !== undefined) planPatch.description = patch.description;
  if (patch.trialDays !== undefined) planPatch.trial_days = patch.trialDays;
  if (metadata) planPatch.metadata = metadata;
  if (Object.keys(planPatch).length > 0) {
    await api.patch(`/catalog/plans/${id}/`, planPatch);
  }

  if (patch.amount !== undefined && patch.currency && patch.interval) {
    await createPriceVersion(id, {
      amount: patch.amount,
      currency: patch.currency,
      interval: patch.interval
    });
  }

  if (patch.status === "active") {
    await api.post(`/catalog/plans/${id}/activate/`);
  } else if (patch.status === "archived") {
    await archiveCatalogPlan(id);
  }
}

export async function archiveCatalogPlan(id: string): Promise<void> {
  await api.post(`/catalog/plans/${id}/archive/`);
}

export async function duplicateCatalogPlan(id: string, sourceName: string): Promise<string> {
  const cloned = await api.post<PlanDto>(`/catalog/plans/${id}/clone/`, {
    new_name: `${sourceName} (copy)`
  });
  return cloned.id;
}
