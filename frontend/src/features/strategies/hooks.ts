"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createStrategy,
  deactivateStrategy,
  listStrategies,
  updateStrategy,
  type StrategyWritePayload,
} from "./api";

export const strategiesKey = ["strategies"] as const;

export function useStrategies(params: { is_active?: boolean } = {}) {
  return useQuery({
    queryKey: [...strategiesKey, params],
    queryFn: () => listStrategies(params),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  // Les trades affichent le nom de leur stratégie : on rafraîchit aussi leurs listes.
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: strategiesKey }),
      queryClient.invalidateQueries({ queryKey: ["trades"] }),
    ]);
}

export function useCreateStrategy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: StrategyWritePayload) => createStrategy(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateStrategy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: StrategyWritePayload }) =>
      updateStrategy(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeactivateStrategy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => deactivateStrategy(id),
    onSuccess: invalidate,
  });
}
