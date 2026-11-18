export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> =
    (opts.body as unknown) instanceof FormData
      ? {}
      : { "Content-Type": "application/json", ...((opts.headers as Record<string, string>) || {}) };
  const res = await fetch(path, { credentials: "include", headers, ...opts });
  if (!res.ok) {
    let d: { detail?: string } = {};
    try {
      d = (await res.json()) as { detail?: string };
    } catch {
      /* 非 JSON 响应体 */
    }
    throw new ApiError(res.status, d.detail || `请求失败(${res.status})`);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export function download(url: string): void {
  window.open(url, "_blank");
}
