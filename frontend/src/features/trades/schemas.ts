import { z } from "zod";

import { isoToZonedInput, nowZonedInput, zonedInputToIso } from "@/lib/datetime";
import { decimalSign } from "@/lib/format";
import type { Trade } from "@/types/api";
import type { TradeWritePayload } from "./api";

/** Accepte « 2,5 » ou « 2.5 » ; normalise en « 2.5 ». */
export const normalizeDecimal = (value: string) => value.trim().replace(",", ".");

const DECIMAL_RE = /^-?\d+([.,]\d+)?$/;
const decimalField = z
  .string()
  .refine((v) => v.trim() === "" || DECIMAL_RE.test(v.trim()), "Nombre attendu (ex. 2,5).");

const positiveDecimal = decimalField.refine(
  (v) => v.trim() === "" || !DECIMAL_RE.test(v.trim()) || decimalSign(normalizeDecimal(v)) === 1,
  "Le RR prévu doit être strictement positif.",
);

const nonNegativeDecimal = decimalField.refine(
  (v) => v.trim() === "" || !v.trim().startsWith("-"),
  "La valeur ne peut pas être négative.",
);

/** Tous les champs sont des chaînes (état du formulaire) ; la conversion se fait dans toPayload. */
export const tradeFormSchema = z.object({
  name: z.string().trim().min(1, "Le nom est obligatoire.").max(200, "200 caractères maximum."),
  trade_date: z.string().min(1, "La date est obligatoire."),
  market_type: z.enum(["FOREX", "METALS", "INDICES", "CRYPTO"], { error: "Choisissez un marché." }),
  asset: z.string().trim().min(1, "L'actif est obligatoire.").max(32, "32 caractères maximum."),
  direction: z.enum(["BUY", "SELL"], { error: "Choisissez un sens." }),
  strategy: z.string(), // "none" ou UUID
  planned_rr: positiveDecimal,
  realized_rr: decimalField,
  entry_price: nonNegativeDecimal,
  stop_loss: nonNegativeDecimal,
  take_profit: nonNegativeDecimal,
  notes: z.string(),
});

export type TradeFormValues = z.infer<typeof tradeFormSchema>;

export const NO_STRATEGY = "none";

export function defaultFormValues(tz: string | undefined): TradeFormValues {
  return {
    name: "",
    trade_date: nowZonedInput(tz),
    market_type: "FOREX",
    asset: "",
    direction: "BUY",
    strategy: NO_STRATEGY,
    planned_rr: "",
    realized_rr: "",
    entry_price: "",
    stop_loss: "",
    take_profit: "",
    notes: "",
  };
}

const toForm = (value: string | null) => (value === null ? "" : value);

export function tradeToFormValues(trade: Trade, tz: string | undefined): TradeFormValues {
  return {
    name: trade.name,
    trade_date: isoToZonedInput(trade.trade_date, tz),
    market_type: trade.market_type,
    asset: trade.asset,
    direction: trade.direction,
    strategy: trade.strategy ?? NO_STRATEGY,
    planned_rr: toForm(trade.planned_rr),
    realized_rr: toForm(trade.realized_rr),
    entry_price: toForm(trade.entry_price),
    stop_loss: toForm(trade.stop_loss),
    take_profit: toForm(trade.take_profit),
    notes: trade.notes,
  };
}

const optionalDecimal = (value: string) => (value.trim() === "" ? null : normalizeDecimal(value));

/**
 * Valeurs du formulaire → corps API.
 * - Aucun `status` ni `user` n'est envoyé (dérivés/imposés côté serveur).
 * - `realized_rr` vide ⇒ null ⇒ trade ouvert (rouvre un trade déjà clôturé).
 */
export function toPayload(values: TradeFormValues, tz: string | undefined): TradeWritePayload {
  return {
    name: values.name.trim(),
    trade_date: zonedInputToIso(values.trade_date, tz) ?? values.trade_date,
    market_type: values.market_type,
    asset: values.asset.trim().toUpperCase(),
    direction: values.direction,
    strategy: values.strategy === NO_STRATEGY ? null : values.strategy,
    planned_rr: optionalDecimal(values.planned_rr),
    realized_rr: optionalDecimal(values.realized_rr),
    entry_price: optionalDecimal(values.entry_price),
    stop_loss: optionalDecimal(values.stop_loss),
    take_profit: optionalDecimal(values.take_profit),
    notes: values.notes,
  };
}
