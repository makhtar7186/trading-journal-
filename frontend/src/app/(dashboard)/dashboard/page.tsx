import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/shared/states";
import { DashboardView } from "@/features/trades/components/dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingRows />}>
      <DashboardView />
    </Suspense>
  );
}
