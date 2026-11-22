import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { LoadingRows } from "@/components/shared/states";
import { TradesList } from "@/features/trades/components/trades-list";

export const metadata: Metadata = { title: "Journal des trades" };

export default function TradesPage() {
  return (
    <>
      <PageHeader title="Journal des trades" description="Tous vos trades, filtrables et triables." />
      <Suspense fallback={<LoadingRows />}>
        <TradesList />
      </Suspense>
    </>
  );
}
