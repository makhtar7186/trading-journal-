import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingRows } from "@/components/shared/states";
import { CalendarView } from "@/features/calendar/components/calendar-view";

export const metadata: Metadata = { title: "Calendrier" };

export default function CalendarPage() {
  return (
    <Suspense fallback={<LoadingRows rows={6} />}>
      <CalendarView />
    </Suspense>
  );
}
