import Link from "next/link";
import { Compass } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-[60vh] flex-1 items-center justify-center px-4">
      <div className="max-w-md text-center">
        <Compass className="mx-auto mb-3 size-10 text-muted-foreground" aria-hidden />
        <h1 className="text-xl font-semibold">Page introuvable</h1>
        <p className="mt-2 text-sm text-muted-foreground">Cette page n&apos;existe pas ou a été déplacée.</p>
        <Button asChild className="mt-5">
          <Link href="/dashboard">Retour au dashboard</Link>
        </Button>
      </div>
    </main>
  );
}
