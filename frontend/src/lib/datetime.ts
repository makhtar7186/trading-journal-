/** Dates : le serveur stocke en UTC ; l'affichage et la saisie suivent le fuseau de l'utilisateur. */

export const DEFAULT_TIMEZONE = "UTC";

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat("fr-FR", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

function safeZone(tz: string | undefined): string {
  return tz && isValidTimeZone(tz) ? tz : DEFAULT_TIMEZONE;
}

/** Décalage (ms) du fuseau `tz` par rapport à UTC à l'instant `utcMs`. */
function zoneOffsetMs(utcMs: number, tz: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date(utcMs));
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
  return asUtc - Math.floor(utcMs / 1000) * 1000;
}

/** "2026-11-10T09:30" saisi dans le fuseau `tz` → ISO UTC. Retourne null si invalide. */
export function zonedInputToIso(value: string, tz: string | undefined): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [y, mo, d, h, mi] = match.slice(1).map(Number);
  const zone = safeZone(tz);
  const guess = Date.UTC(y, mo - 1, d, h, mi);
  let utc = guess - zoneOffsetMs(guess, zone);
  // Seconde passe : corrige les changements d'heure (DST) proches de l'instant visé.
  utc = guess - zoneOffsetMs(utc, zone);
  const date = new Date(utc);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** ISO UTC → valeur "YYYY-MM-DDTHH:mm" pour <input type="datetime-local"> dans le fuseau `tz`. */
export function isoToZonedInput(iso: string, tz: string | undefined): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: safeZone(tz),
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

export function nowZonedInput(tz: string | undefined): string {
  return isoToZonedInput(new Date().toISOString(), tz);
}

export function formatDateTime(iso: string | null, tz: string | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    timeZone: safeZone(tz),
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

/** Heure seule (ex. « 09:30 ») dans le fuseau `tz`. */
export function formatTime(iso: string | null, tz: string | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", { timeZone: safeZone(tz), timeStyle: "short" }).format(date);
}

export function formatDate(iso: string | null, tz: string | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", { timeZone: safeZone(tz), dateStyle: "medium" }).format(date);
}

/** Date du jour (YYYY-MM-DD) dans le fuseau `tz`. */
export function todayIn(tz: string | undefined, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: safeZone(tz),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Ajoute (ou retire) des jours à une date YYYY-MM-DD, sans effet de fuseau ni d'heure d'été. */
export function shiftDate(ymd: string, days: number): string {
  const [y, m, d] = ymd.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function startOfYear(ymd: string): string {
  return `${ymd.slice(0, 4)}-01-01`;
}

export function listTimeZones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  const zones = intl.supportedValuesOf?.("timeZone") ?? [];
  return zones.includes("UTC") ? zones : ["UTC", ...zones];
}
