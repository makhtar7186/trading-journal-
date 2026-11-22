import type { Metadata } from "next";

import { TradeEdit } from "@/features/trades/components/trade-edit";

export const metadata: Metadata = { title: "Modifier le trade" };

export default async function EditTradePage({ params }: PageProps<"/trades/[id]/edit">) {
  const { id } = await params;
  return <TradeEdit id={id} />;
}
