const stripTrailingSlash = (url: string) => url.replace(/\/+$/, "");

const envUrl = (value: string | undefined, fallback: string) =>
  stripTrailingSlash(value && value.trim().length > 0 ? value : fallback);

export const customerPortalBaseUrl = envUrl(
  import.meta.env.VITE_CUSTOMER_PORTAL_URL,
  "https://portal.subpilot.kylodo.com"
);

export const publicApiBaseUrl = envUrl(
  import.meta.env.VITE_PUBLIC_API_BASE_URL,
  "https://api.subpilot.kylodo.com/api/v1"
);

export function customerPortalUrl(slug: string, path = "") {
  const cleanedSlug = slug.trim().replace(/^\/+|\/+$/g, "") || "your-brand";
  const cleanedPath = path.trim().replace(/^\/+/, "");
  return `${customerPortalBaseUrl}/${cleanedSlug}${cleanedPath ? `/${cleanedPath}` : ""}`;
}
