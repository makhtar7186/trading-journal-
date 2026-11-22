/**
 * Calendrier : arithmétique de dates pure (YYYY-MM-DD / YYYY-MM), en UTC, sans effet de fuseau
 * ni d'heure d'été. Semaines du lundi au dimanche.
 */
import { shiftDate, todayIn } from "./datetime";

const MONTH_RE = /^(\d{4})-(0[1-9]|1[0-2])$/;

export function isValidMonth(value: string | null | undefined): value is string {
  if (!value) return false;
  const match = MONTH_RE.exec(value);
  return !!match && Number(match[1]) >= 2000 && Number(match[1]) <= 2100;
}

export function currentMonth(tz: string | undefined, now: Date = new Date()): string {
  return todayIn(tz, now).slice(0, 7);
}

/** "2026-11" + 1 → "2026-12" ; "2026-12" + 1 → "2027-01". */
export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const index = y * 12 + (m - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** Jour de la semaine, lundi = 0 … dimanche = 6. */
export function weekdayIndex(ymd: string): number {
  const [y, m, d] = ymd.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function daysInMonth(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

export function monthOf(ymd: string): string {
  return ymd.slice(0, 7);
}

/**
 * Grille du mois : semaines complètes (4 à 6 lignes de 7 jours, lundi en premier).
 * Les jours des mois voisins complètent la première et la dernière semaine.
 */
export function monthGrid(month: string): string[][] {
  const first = `${month}-01`;
  const start = shiftDate(first, -weekdayIndex(first));
  const last = `${month}-${String(daysInMonth(month)).padStart(2, "0")}`;
  const end = shiftDate(last, 6 - weekdayIndex(last));

  const weeks: string[][] = [];
  for (let cursor = start; cursor <= end; ) {
    const week = Array.from({ length: 7 }, (_, i) => shiftDate(cursor, i));
    weeks.push(week);
    cursor = shiftDate(cursor, 7);
  }
  return weeks;
}

const utcDate = (ymd: string) => {
  const [y, m, d] = ymd.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
};

/** "2026-11" → "novembre 2026". */
export function monthLabel(month: string): string {
  return new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" }).format(utcDate(`${month}-01`));
}

/** "2026-11-10" → "mardi 10 novembre 2026". */
export function dayLabel(ymd: string): string {
  return new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(
    utcDate(ymd),
  );
}

/** "2026-11-10" → "mardi 10 novembre". */
export function dayLabelShort(ymd: string): string {
  return new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(utcDate(ymd));
}

/** En-têtes de colonnes, lundi en premier : { short: "lun.", long: "lundi" }. */
export function weekdayHeaders(): { short: string; long: string }[] {
  const monday = "2026-11-09"; // un lundi
  return Array.from({ length: 7 }, (_, i) => {
    const date = utcDate(shiftDate(monday, i));
    return {
      short: new Intl.DateTimeFormat("fr-FR", { weekday: "short", timeZone: "UTC" }).format(date),
      long: new Intl.DateTimeFormat("fr-FR", { weekday: "long", timeZone: "UTC" }).format(date),
    };
  });
}

export function dayOfMonth(ymd: string): number {
  return Number(ymd.slice(8, 10));
}
