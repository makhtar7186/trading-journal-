"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "@/services/api-client";
import type { User } from "@/types/api";
import { fetchMe } from "./api";

export const ME_KEY = ["me"] as const;

interface AuthState {
  user: User | null;
  isLoading: boolean;
  /** Erreur autre que « non connecté » (serveur injoignable, 5xx…). */
  error: Error | null;
  refetch: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery<User | null, Error>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await fetchMe();
      } catch (error) {
        // 401/403 = pas de session : état normal, pas une erreur.
        if (error instanceof ApiError && error.isAuthError) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });

  return (
    <AuthContext.Provider
      value={{
        user: query.data ?? null,
        isLoading: query.isLoading,
        error: query.error,
        refetch: () => void query.refetch(),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>.");
  return ctx;
}

/** Fuseau d'affichage de l'utilisateur connecté. */
export function useTimeZone(): string {
  return useAuth().user?.timezone ?? "UTC";
}
