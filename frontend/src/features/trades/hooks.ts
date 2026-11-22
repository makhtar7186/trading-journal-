"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { analyticsKey } from "@/features/analytics/hooks";
import {
  createTrade,
  deleteTrade,
  getTrade,
  listTrades,
  updateTrade,
  type TradeListParams,
  type TradeWritePayload,
} from "./api";

export const tradesKey = ["trades"] as const;

/** Un trade modifié change aussi les statistiques : on rafraîchit les deux. */
function invalidateTradeData(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: tradesKey }),
    queryClient.invalidateQueries({ queryKey: analyticsKey }),
  ]);
}

export function useTrades(params: TradeListParams) {
  return useQuery({
    queryKey: [...tradesKey, "list", params],
    queryFn: () => listTrades(params),
    placeholderData: keepPreviousData,
  });
}

export function useTrade(id: string) {
  return useQuery({
    queryKey: [...tradesKey, "detail", id],
    queryFn: () => getTrade(id),
  });
}

export function useCreateTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradeWritePayload) => createTrade(payload),
    onSuccess: () => invalidateTradeData(queryClient),
  });
}

export function useUpdateTrade(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradeWritePayload) => updateTrade(id, payload),
    onSuccess: () => invalidateTradeData(queryClient),
  });
}

export function useDeleteTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTrade(id),
    onSuccess: () => invalidateTradeData(queryClient),
  });
}
