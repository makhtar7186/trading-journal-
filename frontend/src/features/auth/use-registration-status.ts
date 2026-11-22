"use client";

import { useQuery } from "@tanstack/react-query";

import { getRegistrationStatus } from "./api";

export const REGISTRATION_KEY = ["registration"] as const;

/** En cas d'erreur (serveur indisponible…), on considère la création de compte comme indisponible. */
export function useRegistrationStatus() {
  return useQuery({
    queryKey: REGISTRATION_KEY,
    queryFn: getRegistrationStatus,
    retry: false,
    staleTime: 60_000,
  });
}
