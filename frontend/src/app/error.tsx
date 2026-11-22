"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Erreur imprévue dans une page : message clair, possibilité de réessayer, aucun détail technique affiché. */
export default function ErrorPage({ error, retry }: { error: unknown; retry: () => void }) {
  const router = useRouter();
  useEffect(() => {
    console.error(error); // visible en développement ; ne contient rien de sensible côté client en production
  }, [error]);

  return (
    <main className="flex min-h-[60vh] flex-1 items-center justify-center px-4">
      <div role="alert" className="max-w-md text-center">
        <AlertTriangle className="mx-auto mb-3 size-10 text-negative" aria-hidden />
        <h1 className="text-xl font-semibold">Une erreur est survenue</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Quelque chose s&apos;est mal passé de notre côté. Vos données ne sont pas affectées. Réessayez ; si le problème
          persiste, rechargez la page.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <Button onClick={() => retry()}>Réessayer</Button>
          <Button variant="outline" onClick={() => router.push("/dashboard")}>
            Retour au dashboard
          </Button>
        </div>
      </div>
    </main>
  );
}
