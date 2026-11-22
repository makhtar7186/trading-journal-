import type { ReactElement } from "react";
import { vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";

import { AuthProvider } from "@/features/auth/auth-provider";
import type { Screenshot, Trade, User } from "@/types/api";

export const TEST_USER: User = { id: "u1", username: "alice", email: "", timezone: "UTC" };

export function makeTrade(overrides: Partial<Trade> = {}): Trade {
  return {
    id: "t1",
    name: "Breakout Londres",
    trade_date: "2026-11-10T09:30:00Z",
    market_type: "FOREX",
    asset: "EURUSD",
    direction: "BUY",
    status: "OPEN",
    planned_rr: "2.0000",
    realized_rr: null,
    strategy: null,
    entry_price: null,
    stop_loss: null,
    take_profit: null,
    notes: "",
    created_at: "2026-11-10T09:30:00Z",
    updated_at: "2026-11-10T09:30:00Z",
    closed_at: null,
    ...overrides,
  };
}

export function makeScreenshot(overrides: Partial<Screenshot> = {}): Screenshot {
  return {
    id: "s1",
    trade: "t1",
    original_filename: "capture.png",
    category: "BEFORE",
    description: "",
    uploaded_at: "2026-11-10T09:30:00Z",
    file_url: "/api/v1/screenshots/s1/file/",
    ...overrides,
  };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export interface RecordedCall {
  method: string;
  path: string; // chemin + query, sans le préfixe /api/v1
  body: unknown;
}

type Handler = (call: RecordedCall) => Response | undefined | Promise<Response | undefined>;

/**
 * Remplace fetch. Session toujours valide (GET /auth/me/) et CSRF no-op par défaut ;
 * `handler` répond aux autres appels. Retourne la liste des appels enregistrés.
 */
export function stubApi(handler: Handler = () => undefined) {
  const calls: RecordedCall[] = [];
  const mock = vi.fn(async (input: string, init?: RequestInit) => {
    const call: RecordedCall = {
      method: (init?.method ?? "GET").toUpperCase(),
      path: String(input).replace(/^\/api\/v1/, ""),
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(call);
    const custom = await handler(call);
    if (custom) return custom;
    if (call.path === "/auth/me/") return jsonResponse(TEST_USER);
    if (call.path === "/auth/csrf/") return jsonResponse(null, 204);
    if (call.path === "/auth/registration/") return jsonResponse({ enabled: false, has_users: true });
    if (call.path.startsWith("/strategies/")) return jsonResponse({ count: 0, next: null, previous: null, results: [] });
    return jsonResponse({ detail: `non géré: ${call.method} ${call.path}` }, 404);
  });
  vi.stubGlobal("fetch", mock);
  return { calls, mock };
}

/** Rend un composant avec React Query + session simulée (fetch doit être stubbé par le test). */
export function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{ui}</AuthProvider>
    </QueryClientProvider>,
  );
}
