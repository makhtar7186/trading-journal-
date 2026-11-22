import { describe, expect, it } from "vitest";

import { makeTrade } from "@/test/utils";
import {
  defaultFormValues,
  NO_STRATEGY,
  toPayload,
  tradeFormSchema,
  tradeToFormValues,
  type TradeFormValues,
} from "./schemas";

const valid = (overrides: Partial<TradeFormValues> = {}): TradeFormValues => ({
  ...defaultFormValues("UTC"),
  name: "EURUSD London",
  asset: "eurusd",
  trade_date: "2026-11-10T09:30",
  ...overrides,
});

function errorsOf(values: TradeFormValues): Record<string, string> {
  const result = tradeFormSchema.safeParse(values);
  if (result.success) return {};
  return Object.fromEntries(result.error.issues.map((i) => [String(i.path[0]), i.message]));
}

describe("validation du formulaire", () => {
  it("accepte un trade minimal", () => {
    expect(errorsOf(valid())).toEqual({});
  });

  it("exige nom et actif non vides (espaces seuls refusés)", () => {
    const errors = errorsOf(valid({ name: "   ", asset: "" }));
    expect(errors.name).toMatch(/obligatoire/);
    expect(errors.asset).toMatch(/obligatoire/);
  });

  it.each(["0", "-1", "-0.5", "0,0"])("refuse un RR prévu non strictement positif : %s", (value) => {
    expect(errorsOf(valid({ planned_rr: value })).planned_rr).toMatch(/strictement positif/);
  });

  it.each(["2,5", "2.5", "0.1", ""])("accepte un RR prévu valide : « %s »", (value) => {
    expect(errorsOf(valid({ planned_rr: value }))).toEqual({});
  });

  it("accepte un RR réalisé négatif, nul ou positif", () => {
    for (const value of ["-1", "0", "3,5", ""]) {
      expect(errorsOf(valid({ realized_rr: value }))).toEqual({});
    }
  });

  it("refuse un RR non numérique", () => {
    expect(errorsOf(valid({ realized_rr: "abc" })).realized_rr).toMatch(/Nombre/);
    expect(errorsOf(valid({ planned_rr: "1,2,3" })).planned_rr).toBeTruthy();
  });

  it("refuse un prix négatif", () => {
    expect(errorsOf(valid({ entry_price: "-1" })).entry_price).toMatch(/négative/);
  });
});

describe("toPayload", () => {
  it("n'envoie jamais status ni user", () => {
    const payload = toPayload(valid({ realized_rr: "2" }), "UTC") as Record<string, unknown>;
    expect(payload).not.toHaveProperty("status");
    expect(payload).not.toHaveProperty("user");
    expect(payload).not.toHaveProperty("user_id");
  });

  it("normalise l'actif, la virgule décimale et la date", () => {
    const payload = toPayload(valid({ planned_rr: "2,5", trade_date: "2026-11-10T09:30" }), "Europe/Paris");
    expect(payload.asset).toBe("EURUSD");
    expect(payload.planned_rr).toBe("2.5");
    expect(payload.trade_date).toBe("2026-11-10T08:30:00.000Z");
  });

  it("champs vides → null ; RR réalisé vide = trade ouvert", () => {
    const payload = toPayload(valid(), "UTC");
    expect(payload.planned_rr).toBeNull();
    expect(payload.realized_rr).toBeNull();
    expect(payload.entry_price).toBeNull();
    expect(payload.strategy).toBeNull();
  });

  it("conserve la stratégie choisie", () => {
    expect(toPayload(valid({ strategy: "s-1" }), "UTC").strategy).toBe("s-1");
    expect(toPayload(valid({ strategy: NO_STRATEGY }), "UTC").strategy).toBeNull();
  });

  it("garde les décimaux en chaîne (pas de float)", () => {
    const payload = toPayload(valid({ realized_rr: "0,1", stop_loss: "1.08500" }), "UTC");
    expect(payload.realized_rr).toBe("0.1");
    expect(payload.stop_loss).toBe("1.08500");
  });
});

describe("tradeToFormValues", () => {
  it("remplit le formulaire depuis un trade clôturé", () => {
    const values = tradeToFormValues(
      makeTrade({ status: "WIN", realized_rr: "3.0000", strategy: "s-1", trade_date: "2026-11-10T08:30:00Z" }),
      "Europe/Paris",
    );
    expect(values.realized_rr).toBe("3.0000");
    expect(values.strategy).toBe("s-1");
    expect(values.trade_date).toBe("2026-11-10T09:30");
  });

  it("transforme les null en chaînes vides", () => {
    const values = tradeToFormValues(makeTrade(), "UTC");
    expect(values.realized_rr).toBe("");
    expect(values.strategy).toBe(NO_STRATEGY);
  });
});
