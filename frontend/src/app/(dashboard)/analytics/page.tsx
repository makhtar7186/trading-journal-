import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/shared/states";
import { AnalyticsView } from "@/features/analytics/components/analytics-view";

export const metadata: Metadata = { title: "Analytics" };

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<LoadingRows />}>
      <AnalyticsView />
    </Suspense>
  );
}
