import { apiFetch, type Query } from "@/services/api-client";
import type { Paginated, Trade } from "@/types/api";

export interface TradeListParams extends Query {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  market_type?: string;
  direction?: string;
  asset?: string;
  strategy?: string;
  date_from?: string;
  date_to?: string;
  ordering?: string;
}

/** Corps accepté par l'API. `status` n'y figure volontairement pas : il est dérivé côté serveur. */
export interface TradeWritePayload {
  name?: string;
  trade_date?: string;
  market_type?: string;
  asset?: string;
  direction?: string;
  strategy?: string | null;
  planned_rr?: string | null;
  realized_rr?: string | null;
  entry_price?: string | null;
  stop_loss?: string | null;
  take_profit?: string | null;
  notes?: string;
}

export const listTrades = (params: TradeListParams) =>
  apiFetch<Paginated<Trade>>("/trades/", { query: params });

export const getTrade = (id: string) => apiFetch<Trade>(`/trades/${id}/`);

export const createTrade = (payload: TradeWritePayload) =>
  apiFetch<Trade>("/trades/", { method: "POST", body: payload });

export const updateTrade = (id: string, payload: TradeWritePayload) =>
  apiFetch<Trade>(`/trades/${id}/`, { method: "PATCH", body: payload });

export const deleteTrade = (id: string) => apiFetch<void>(`/trades/${id}/`, { method: "DELETE" });
