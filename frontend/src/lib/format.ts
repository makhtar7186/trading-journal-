/** Formatage des valeurs en R. Les décimaux arrivent en chaîne ; on ne fait aucun calcul financier ici. */

export type Tone = "positive" | "negative" | "neutral";

/** Signe d'une chaîne décimale sans passer par un float. */
export function decimalSign(value: string | null | undefined): -1 | 0 | 1 | null {
  if (value === null || value === undefined || value === "") return null;
  const trimmed = value.trim();
  if (!/^-?\d+(\.\d+)?$/.test(trimmed)) return null;
  const negative = trimmed.startsWith("-");
  const isZero = /^-?0+(\.0+)?$/.test(trimmed);
  if (isZero) return 0;
  return negative ? -1 : 1;
}

export function toneOf(value: string | null | undefined): Tone {
  const sign = decimalSign(value);
  if (sign === 1) return "positive";
  if (sign === -1) return "negative";
  return "neutral";
}

/** "2.5000" → "+2,5 R" ; "-1.0000" → "−1 R" ; null → "—". Zéros inutiles retirés. */
export function formatR(value: string | null | undefined, options: { signed?: boolean } = {}): string {
  const sign = decimalSign(value);
  if (sign === null || value == null) return "—";
  const [intRaw, fracRaw = ""] = value.trim().replace(/^-/, "").split(".");
  const intPart = intRaw.replace(/^0+(?=\d)/, "");
  const frac = fracRaw.replace(/0+$/, "");
  const number = frac ? `${intPart},${frac}` : intPart;
  const prefix = sign === -1 ? "−" : options.signed && sign === 1 ? "+" : "";
  return `${prefix}${number} R`;
}

/** "57.1400" → "57,14 %" ; "100.00" → "100 %" ; null → "—". */
export function formatPercent(value: string | null | undefined): string {
  if (value === null || value === undefined || !/^-?\d+(\.\d+)?$/.test(value.trim())) return "—";
  const [int, frac = ""] = value.trim().split(".");
  const trimmed = frac.replace(/0+$/, "");
  return `${trimmed ? `${int},${trimmed}` : int} %`;
}

/** Ratio sans unité (profit factor) : "2.5000" → "2,5" ; null → "—". */
export function formatRatio(value: string | null | undefined): string {
  if (value === null || value === undefined || !/^-?\d+(\.\d+)?$/.test(value.trim())) return "—";
  const [int, frac = ""] = value.trim().split(".");
  const trimmed = frac.replace(/0+$/, "");
  return trimmed ? `${int},${trimmed}` : int;
}

/** Prix : affichage tel quel, zéros de fin retirés. */
export function formatPrice(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  if (!value.includes(".")) return value;
  return value.replace(/0+$/, "").replace(/\.$/, "").replace(".", ",");
}

export const TONE_CLASS: Record<Tone, string> = {
  positive: "text-positive",
  negative: "text-negative",
  neutral: "text-muted-foreground",
};
