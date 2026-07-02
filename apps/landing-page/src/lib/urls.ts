const stripTrailingSlash = (url: string) => url.replace(/\/+$/, "");

const envUrl = (value: string | undefined, fallback: string) =>
  stripTrailingSlash(value && value.trim().length > 0 ? value : fallback);

export const merchantAppUrl = envUrl(
  import.meta.env.VITE_MERCHANT_APP_URL,
  "https://app.subpilot.kylodo.com"
);

export const customerPortalUrl = envUrl(
  import.meta.env.VITE_CUSTOMER_PORTAL_URL,
  "https://portal.subpilot.kylodo.com"
);

export const platformAdminUrl = envUrl(
  import.meta.env.VITE_PLATFORM_ADMIN_URL,
  "https://platform-admin.subpilot.kylodo.com"
);

export function isExternalUrl(to: string) {
  return /^https?:\/\//i.test(to);
}

export function resolveProductUrl(to: string) {
  if (to.startsWith("/merchant")) return merchantAppUrl;
  if (to.startsWith("/admin")) return platformAdminUrl;
  return to;
}
