"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import { ErrorState, LoadingRows } from "@/components/shared/states";
import { useAuth } from "@/features/auth/auth-provider";

/**
 * Garde d'accès côté client : la sécurité réelle reste côté API (session + permissions).
 * Ce layout évite seulement d'afficher l'interface sans session.
 */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading, error, refetch } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !error && !user) router.replace("/login");
  }, [isLoading, error, user, router]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-md p-8">
        <ErrorState message="Impossible de joindre le serveur." onRetry={refetch} />
      </div>
    );
  }
  if (isLoading || !user) {
    return (
      <div className="mx-auto w-full max-w-md p-8">
        <LoadingRows rows={3} />
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}
