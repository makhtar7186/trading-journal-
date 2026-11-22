"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { getCalendar, type CalendarParams } from "./api";

// Sous la clé ["analytics", …] : un trade modifié rafraîchit aussi le calendrier.
export const useCalendar = (params: CalendarParams) =>
  useQuery({
    queryKey: ["analytics", "calendar", params],
    queryFn: () => getCalendar(params),
    placeholderData: keepPreviousData,
  });
