"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { logout } from "./api";
import { ME_KEY } from "./auth-provider";

/**
 * Déconnexion : appelle l'API, vide le cache puis ramène à la page de connexion.
 *
 * `queryClient.clear()` seul ne suffit PAS : l'observateur de `["me"]` (AuthProvider, au-dessus des pages) garde
 * l'ancien utilisateur en mémoire, la page de connexion le croit connecté et renvoie au tableau de bord.
 * On fixe donc explicitement `["me"]` à `null` et on retire toutes les autres données.
 */
export function useLogout(): () => Promise<void> {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useCallback(async () => {
    try {
      await logout();
    } catch {
      // Session déjà expirée ou serveur injoignable : on déconnecte quand même localement.
    }
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] });
    queryClient.setQueryData(ME_KEY, null);
    router.replace("/login");
  }, [queryClient, router]);
}
