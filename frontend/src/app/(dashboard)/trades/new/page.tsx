import type { Metadata } from "next";

import { PageHeader } from "@/components/shared/page-header";
import { TradeForm } from "@/features/trades/components/trade-form";

export const metadata: Metadata = { title: "Nouveau trade" };

export default function NewTradePage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Ajouter un trade" description="Après l'enregistrement, ajoutez vos captures d'écran depuis la fiche du trade." />
      <TradeForm />
    </div>
  );
}
