"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ScreenshotCategory } from "@/types/api";
import {
  deleteScreenshot,
  listScreenshots,
  updateScreenshot,
  uploadScreenshot,
  type UploadOptions,
} from "./api";

export const screenshotsKey = (tradeId: string) => ["screenshots", tradeId] as const;

export function useScreenshots(tradeId: string) {
  return useQuery({
    queryKey: screenshotsKey(tradeId),
    queryFn: () => listScreenshots(tradeId),
  });
}

export function useUploadScreenshot(tradeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (options: Omit<UploadOptions, "tradeId">) => uploadScreenshot({ tradeId, ...options }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: screenshotsKey(tradeId) }),
  });
}

export function useUpdateScreenshot(tradeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string; category?: ScreenshotCategory; description?: string }) =>
      updateScreenshot(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: screenshotsKey(tradeId) }),
  });
}

export function useDeleteScreenshot(tradeId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteScreenshot(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: screenshotsKey(tradeId) }),
  });
}
