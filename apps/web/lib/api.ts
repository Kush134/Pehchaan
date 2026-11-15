export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (
    options.method &&
    options.method !== "GET" &&
    !headers.has("Idempotency-Key")
  )
    headers.set("Idempotency-Key", crypto.randomUUID());
  const cacheable = (!options.method || options.method === "GET") && path.startsWith("/business/");
  const cacheKey = "pehchaan-business-v1:" + path;
  function saved(): T | undefined {
    if (!cacheable || typeof window === "undefined") return undefined;
    try {
      const snapshot = JSON.parse(localStorage.getItem(cacheKey) || "null");
      if (!snapshot?.cached_at || Date.now() - Date.parse(snapshot.cached_at) > 86400000) return undefined;
      window.dispatchEvent(new CustomEvent("pehchaan-cached-data", { detail: { cached_at: snapshot.cached_at } }));
      return snapshot.data as T;
    } catch { return undefined; }
  }
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, { ...options, headers }); }
  catch (error) { const cached = saved(); if (cached !== undefined) return cached; throw error; }
  if ([502,503,504].includes(response.status)) { const cached = saved(); if (cached !== undefined) return cached; }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message =
      typeof data.detail === "string"
        ? data.detail
        : typeof data.error === "string"
          ? data.error
          : data.error?.message ||
            JSON.stringify(data.detail || "Request failed. Please try again.");
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  const result = await response.json() as T;
  if (cacheable && typeof window !== "undefined") {
    try { localStorage.setItem(cacheKey, JSON.stringify({data: result, cached_at: new Date().toISOString()})); } catch { /* Device storage can be disabled. */ }
  }
  return result;
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
