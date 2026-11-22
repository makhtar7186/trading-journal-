import { apiFetch } from "@/services/api-client";
import type { Paginated, Strategy } from "@/types/api";

export interface StrategyWritePayload {
  name?: string;
  description?: string;
  entry_rules?: string;
  exit_rules?: string;
  is_active?: boolean;
}

export const listStrategies = (params: { is_active?: boolean; page_size?: number } = {}) =>
  apiFetch<Paginated<Strategy>>("/strategies/", { query: { page_size: 100, ...params } });

export const createStrategy = (payload: StrategyWritePayload) =>
  apiFetch<Strategy>("/strategies/", { method: "POST", body: payload });

export const updateStrategy = (id: string, payload: StrategyWritePayload) =>
  apiFetch<Strategy>(`/strategies/${id}/`, { method: "PATCH", body: payload });

/** DELETE désactive la stratégie côté serveur ; l'historique des trades est conservé. */
export const deactivateStrategy = (id: string) =>
  apiFetch<void>(`/strategies/${id}/`, { method: "DELETE" });
