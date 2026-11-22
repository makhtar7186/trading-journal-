"use client";

import { useState, type ReactNode } from "react";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { toast } from "sonner";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, ME_KEY } from "@/features/auth/auth-provider";
import { ApiError } from "@/services/api-client";

/**
 * Session expirée en cours d'utilisation : n'importe quelle requête qui reçoit 401/403 invalide la session
 * locale, ce qui renvoie l'utilisateur vers /login (voir le layout du dashboard). La requête « me » gère
 * déjà ce cas elle-même, et un échec de connexion (400) n'est pas concerné.
 */
function handleAuthError(client: QueryClient, error: unknown, isMe: boolean) {
  if (isMe || !(error instanceof ApiError) || !error.isAuthError) return;
  if (client.getQueryData(ME_KEY) === null) return; // déjà déconnecté
  client.setQueryData(ME_KEY, null);
  toast.error("Votre session a expiré. Reconnectez-vous.");
}

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => handleAuthError(client, error, query.queryKey[0] === ME_KEY[0]),
    }),
    mutationCache: new MutationCache({
      onError: (error) => handleAuthError(client, error, false),
    }),
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Inutile de réessayer une requête refusée (401/403/404) ; on réessaie une fois pour le reste.
        retry: (failureCount, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && failureCount < 1,
      },
    },
  });
  return client;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </QueryClientProvider>
  );
}
