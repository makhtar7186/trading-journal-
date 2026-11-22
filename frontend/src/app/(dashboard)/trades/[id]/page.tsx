import type { Metadata } from "next";

import { TradeDetail } from "@/features/trades/components/trade-detail";

export const metadata: Metadata = { title: "Fiche du trade" };

export default async function TradePage({ params }: PageProps<"/trades/[id]">) {
  const { id } = await params;
  return <TradeDetail id={id} />;
}
