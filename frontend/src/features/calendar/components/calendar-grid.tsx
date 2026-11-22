"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { dayLabelShort, dayOfMonth, daysInMonth, monthGrid, monthOf, shiftMonth, weekdayHeaders } from "@/lib/calendar";
import { shiftDate } from "@/lib/datetime";
import { formatR, toneOf } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CalendarDay } from "@/types/api";

const HEADERS = weekdayHeaders();

/** Résultat compact pour une cellule : "+2", "−1,5", "0" (sans l'unité, qui figure dans le libellé accessible). */
function compactR(value: string): string {
  return formatR(value, { signed: true }).replace(/ R$/, "");
}

function ariaLabelFor(date: string, day: CalendarDay | undefined): string {
  const label = dayLabelShort(date);
  if (!day) return `${label} : aucun trade`;
  const parts: string[] = [];
  if (day.total_r !== null) {
    parts.push(`${formatR(day.total_r, { signed: true })}, ${day.closed_trades} trade${day.closed_trades > 1 ? "s" : ""} clôturé${day.closed_trades > 1 ? "s" : ""}`);
  }
  if (day.open_trades > 0) parts.push(`${day.open_trades} ouvert${day.open_trades > 1 ? "s" : ""}`);
  return `${label} : ${parts.join(", ")}`;
}

/**
 * Grille mensuelle (lundi en premier). Motif ARIA « grid » à tabulation itinérante : une seule cellule
 * dans l'ordre de tabulation ; flèches, Début/Fin (ligne) et PageHaut/PageBas (mois) pour naviguer.
 * Le résultat du jour est écrit avec son signe (jamais la couleur seule).
 */
export function CalendarGrid({
  month,
  days,
  selectedDay,
  today,
  onSelectDay,
  onMonthChange,
}: {
  month: string;
  days: CalendarDay[];
  selectedDay: string | null;
  today: string;
  onSelectDay: (date: string) => void;
  onMonthChange: (month: string) => void;
}) {
  const weeks = monthGrid(month);
  const byDate = new Map(days.map((d) => [d.date, d]));
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const pendingFocus = useRef<string | null>(null);

  const initialFocus = selectedDay ?? (monthOf(today) === month ? today : `${month}-01`);
  const [focused, setFocused] = useState(initialFocus);
  const focusable = monthOf(focused) === month ? focused : initialFocus;

  // Après un changement de mois déclenché au clavier, replace le focus sur le jour visé.
  useEffect(() => {
    const target = pendingFocus.current;
    if (target && monthOf(target) === month) {
      pendingFocus.current = null;
      buttons.current.get(target)?.focus();
    }
  }, [month, days]);

  function moveTo(date: string) {
    if (monthOf(date) === month) {
      setFocused(date);
      buttons.current.get(date)?.focus();
    } else {
      pendingFocus.current = date;
      setFocused(date);
      onMonthChange(monthOf(date));
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, date: string) {
    const weekStart = shiftDate(date, -((new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7));
    const targets: Record<string, string> = {
      ArrowLeft: shiftDate(date, -1),
      ArrowRight: shiftDate(date, 1),
      ArrowUp: shiftDate(date, -7),
      ArrowDown: shiftDate(date, 7),
      Home: weekStart,
      End: shiftDate(weekStart, 6),
    };
    if (event.key === "PageUp" || event.key === "PageDown") {
      event.preventDefault();
      const delta = event.key === "PageUp" ? -1 : 1;
      const targetMonth = shiftMonth(month, delta);
      const dayNumber = Math.min(dayOfMonth(date), daysInMonth(targetMonth)); // 31 janv. → 28 févr.
      moveTo(`${targetMonth}-${String(dayNumber).padStart(2, "0")}`);
      return;
    }
    const target = targets[event.key];
    if (target) {
      event.preventDefault();
      moveTo(target);
    }
  }

  return (
    <div role="grid" aria-label={`Calendrier des trades, ${month}`} className="w-full">
      <div role="row" className="grid grid-cols-7 gap-1 pb-1">
        {HEADERS.map((h) => (
          <div key={h.long} role="columnheader" aria-label={h.long} className="py-1 text-center text-xs font-medium text-muted-foreground">
            {h.short.replace(".", "")}
          </div>
        ))}
      </div>
      {weeks.map((week) => (
        <div role="row" key={week[0]} className="grid grid-cols-7 gap-1 pb-1">
          {week.map((date) => {
            const inMonth = monthOf(date) === month;
            if (!inMonth) {
              // Jours des mois voisins : repères visuels, non interactifs.
              return (
                <div key={date} role="gridcell" aria-disabled="true" className="min-h-14 rounded-lg p-1.5 text-xs text-muted-foreground/40 sm:min-h-20" aria-label={dayLabelShort(date)}>
                  <span aria-hidden>{dayOfMonth(date)}</span>
                </div>
              );
            }
            const day = byDate.get(date);
            const tone = day?.total_r != null ? toneOf(day.total_r) : null;
            const isSelected = selectedDay === date;
            const isToday = date === today;
            return (
              <div key={date} role="gridcell" aria-selected={isSelected}>
                <button
                  type="button"
                  ref={(el) => {
                    if (el) buttons.current.set(date, el);
                    else buttons.current.delete(date);
                  }}
                  tabIndex={focusable === date ? 0 : -1}
                  aria-label={ariaLabelFor(date, day)}
                  aria-pressed={isSelected}
                  aria-current={isToday ? "date" : undefined}
                  onClick={() => {
                    setFocused(date);
                    onSelectDay(date);
                  }}
                  onFocus={() => setFocused(date)}
                  onKeyDown={(e) => onKeyDown(e, date)}
                  className={cn(
                    "flex min-h-14 w-full flex-col justify-between rounded-lg border p-1.5 text-left transition-colors sm:min-h-20",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    tone === "positive" && "border-positive/30 bg-positive/10",
                    tone === "negative" && "border-negative/30 bg-negative/10",
                    tone === "neutral" && "border-border bg-muted",
                    !tone && (day ? "border-primary/30 bg-primary/10" : "border-border bg-card hover:bg-muted/60"),
                    isSelected && "ring-2 ring-primary",
                    isToday && !isSelected && "border-foreground/50",
                  )}
                >
                  <span className={cn("text-xs", isToday ? "font-bold" : "text-muted-foreground")} aria-hidden>
                    {dayOfMonth(date)}
                  </span>
                  <span className="space-y-0.5" aria-hidden>
                    {day?.total_r != null && (
                      <span
                        className={cn(
                          "tabular block text-xs font-semibold sm:text-sm",
                          tone === "positive" && "text-positive",
                          tone === "negative" && "text-negative",
                        )}
                      >
                        {compactR(day.total_r)}
                      </span>
                    )}
                    {day && day.open_trades > 0 && (
                      <span className="block text-[10px] leading-none text-indigo-300 sm:text-xs">
                        ● {day.open_trades}
                        <span className="hidden sm:inline"> ouvert{day.open_trades > 1 ? "s" : ""}</span>
                      </span>
                    )}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
