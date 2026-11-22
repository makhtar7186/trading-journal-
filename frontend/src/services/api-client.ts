/**
 * Client HTTP unique. Les appels passent par le proxy same-origin de Next (/api → Django),
 * donc le cookie de session est envoyé automatiquement et le CSRF reste simple.
 */
export const API_BASE = "/api/v1";
const BASE = API_BASE;
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fieldErrors: FieldErrors = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isAuthError() {
    return this.status === 401 || this.status === 403;
  }
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function ensureCsrfToken(): Promise<string | null> {
  const existing = readCookie("tj_csrftoken");
  if (existing) return existing;
  await fetch(`${BASE}/auth/csrf/`, { credentials: "include", cache: "no-store" });
  return readCookie("tj_csrftoken");
}

/** Convertit une réponse d'erreur DRF en ApiError (message + erreurs par champ). */
export function toApiError(status: number, data: unknown): ApiError {
  const fieldErrors: FieldErrors = {};
  let message = `Erreur ${status}`;

  if (data && typeof data === "object" && !Array.isArray(data)) {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") {
      message = record.detail;
    }
    for (const [key, value] of Object.entries(record)) {
      if (key === "detail") continue;
      if (Array.isArray(value)) fieldErrors[key] = value.map(String);
      else if (typeof value === "string") fieldErrors[key] = [value];
    }
    if (typeof record.detail !== "string" && Object.keys(fieldErrors).length > 0) {
      message = "Certains champs sont invalides.";
    }
  } else if (Array.isArray(data)) {
    message = data.map(String).join(" ");
  }

  if (status === 429) message = "Trop de tentatives. Réessayez dans une minute.";
  if (status === 403 && message.startsWith("Erreur")) message = "Accès refusé.";
  if (status >= 500) message = "Erreur serveur. Réessayez plus tard.";
  return new ApiError(status, message, fieldErrors);
}

export type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (!SAFE_METHODS.has(method)) {
    const token = await ensureCsrfToken();
    if (token) headers["X-CSRFToken"] = token;
  }

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}${buildQuery(options.query)}`, {
      method,
      headers,
      credentials: "include",
      // Données privées et mutables : jamais servies depuis le cache HTTP du navigateur.
      cache: "no-store",
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Serveur injoignable. Vérifiez votre connexion.");
  }

  if (response.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!response.ok) throw toApiError(response.status, data);
  return data as T;
}
