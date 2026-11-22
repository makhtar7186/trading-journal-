import { describe, expect, it } from "vitest";

import { DEFAULT_FILTERS, hasActiveFilters, parseFilterState, serializeFilterState, toApiParams, type FilterState } from "./filters";

const state = (patch: Partial<FilterState> = {}): FilterState => ({ ...DEFAULT_FILTERS, ...patch });
// 15 nov. 2026 à 23h30 UTC = déjà le 16 nov. à Paris (UTC+1)
const NOW = new Date("2026-11-15T23:30:00Z");

describe("toApiParams — périodes relatives au jour courant de l'utilisateur", () => {
  it("« Tout » n'envoie aucune borne", () => {
    expect(toApiParams(state(), "UTC", NOW)).toEqual({});
  });

  it("7 / 30 / 90 jours incluent aujourd'hui", () => {
    expect(toApiParams(state({ range: "7d" }), "UTC", NOW)).toEqual({ date_from: "2026-11-09", date_to: "2026-11-15" });
    expect(toApiParams(state({ range: "30d" }), "UTC", NOW)).toEqual({ date_from: "2026-10-17", date_to: "2026-11-15" });
    expect(toApiParams(state({ range: "90d" }), "UTC", NOW)).toEqual({ date_from: "2026-08-18", date_to: "2026-11-15" });
  });

  it("« aujourd'hui » dépend du fuseau de l'utilisateur", () => {
    expect(toApiParams(state({ range: "7d" }), "Europe/Paris", NOW).date_to).toBe("2026-11-16");
    expect(toApiParams(state({ range: "7d" }), "UTC", NOW).date_to).toBe("2026-11-15");
    expect(toApiParams(state({ range: "7d" }), "Pacific/Auckland", NOW).date_to).toBe("2026-11-16");
  });

  it("cette année commence au 1er janvier", () => {
    expect(toApiParams(state({ range: "ytd" }), "UTC", NOW)).toEqual({ date_from: "2026-01-01", date_to: "2026-11-15" });
  });

  it("personnalisée : utilise les dates saisies, ignore celles vides", () => {
    expect(toApiParams(state({ range: "custom", date_from: "2026-01-05", date_to: "2026-02-01" }), "UTC", NOW)).toEqual({
      date_from: "2026-01-05",
      date_to: "2026-02-01",
    });
    expect(toApiParams(state({ range: "custom", date_from: "2026-01-05" }), "UTC", NOW)).toEqual({ date_from: "2026-01-05" });
    expect(toApiParams(state({ range: "custom" }), "UTC", NOW)).toEqual({});
  });

  it("les dates personnalisées d'un ancien état ne fuient pas dans un préréglage", () => {
    const params = toApiParams(state({ range: "7d", date_from: "2020-01-01", date_to: "2020-02-02" }), "UTC", NOW);
    expect(params.date_from).toBe("2026-11-09");
  });

  it("ajoute marché, actif et stratégie quand ils sont choisis", () => {
    const params = toApiParams(state({ market_type: "CRYPTO", asset: "BTCUSD", strategy: "none" }), "UTC", NOW);
    expect(params).toEqual({ market_type: "CRYPTO", asset: "BTCUSD", strategy: "none" });
  });
});

describe("état des filtres dans l'URL", () => {
  it("valeurs par défaut quand l'URL est vide ou invalide", () => {
    expect(parseFilterState(new URLSearchParams(""))).toEqual(DEFAULT_FILTERS);
    expect(parseFilterState(new URLSearchParams("range=n-importe-quoi")).range).toBe("all");
  });

  it("n'écrit que ce qui diffère des défauts", () => {
    expect(serializeFilterState(state())).toBe("");
    expect(serializeFilterState(state({ range: "30d" }))).toBe("range=30d");
    expect(serializeFilterState(state({ range: "30d", market_type: "FOREX" }))).toBe("range=30d&market_type=FOREX");
  });

  it("n'écrit les dates que pour la période personnalisée", () => {
    expect(serializeFilterState(state({ range: "30d", date_from: "2026-01-01" }))).toBe("range=30d");
    expect(serializeFilterState(state({ range: "custom", date_from: "2026-01-01", date_to: "2026-02-01" }))).toBe(
      "range=custom&date_from=2026-01-01&date_to=2026-02-01",
    );
  });

  it("aller-retour sans perte", () => {
    const original = state({ range: "custom", date_from: "2026-01-01", date_to: "2026-02-01", asset: "XAUUSD", strategy: "abc" });
    expect(parseFilterState(new URLSearchParams(serializeFilterState(original)))).toEqual(original);
  });

  it("détecte les filtres actifs", () => {
    expect(hasActiveFilters(state())).toBe(false);
    expect(hasActiveFilters(state({ asset: "EURUSD" }))).toBe(true);
    expect(hasActiveFilters(state({ range: "7d" }))).toBe(true);
  });
});
