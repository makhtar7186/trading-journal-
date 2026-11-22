import { describe, expect, it } from "vitest";

import { decimalSign, formatPercent, formatPrice, formatR, formatRatio, toneOf } from "./format";

describe("formatPercent / formatRatio", () => {
  it("pourcentage : virgule, zéros inutiles retirés", () => {
    expect(formatPercent("57.14")).toBe("57,14 %");
    expect(formatPercent("100.00")).toBe("100 %");
    expect(formatPercent("50.00")).toBe("50 %");
    expect(formatPercent("0.00")).toBe("0 %");
    expect(formatPercent("33.30")).toBe("33,3 %");
  });

  it("ratio : sans unité", () => {
    expect(formatRatio("2.5000")).toBe("2,5");
    expect(formatRatio("1.0000")).toBe("1");
    expect(formatRatio("0.6667")).toBe("0,6667");
  });

  it("non défini → tiret (jamais 0)", () => {
    for (const value of [null, undefined, "", "abc"]) {
      expect(formatPercent(value as string | null)).toBe("—");
      expect(formatRatio(value as string | null)).toBe("—");
    }
  });
});

describe("decimalSign", () => {
  it.each([
    ["2.5", 1],
    ["0.0001", 1],
    ["-1", -1],
    ["-0.0001", -1],
    ["0", 0],
    ["0.0000", 0],
    ["-0.00", 0],
  ])("%s → %i", (value, expected) => {
    expect(decimalSign(value)).toBe(expected);
  });

  it.each([null, undefined, "", "abc", "1,5", "--1"])("%s → null (non défini)", (value) => {
    expect(decimalSign(value as string | null | undefined)).toBeNull();
  });
});

describe("formatR", () => {
  it("affiche le signe et retire les zéros inutiles", () => {
    expect(formatR("2.5000", { signed: true })).toBe("+2,5 R");
    expect(formatR("3.0000", { signed: true })).toBe("+3 R");
    expect(formatR("-1.0000", { signed: true })).toBe("−1 R");
    expect(formatR("0.0000", { signed: true })).toBe("0 R");
  });

  it("n'ajoute pas de + sans l'option signed", () => {
    expect(formatR("2.5000")).toBe("2,5 R");
    expect(formatR("-2.5000")).toBe("−2,5 R");
  });

  it("garde la précision d'un décimal sans passer par un float", () => {
    expect(formatR("0.1000")).toBe("0,1 R");
    expect(formatR("1234567.1234")).toBe("1234567,1234 R");
  });

  it("affiche un tiret quand la valeur est absente (jamais 0)", () => {
    expect(formatR(null)).toBe("—");
    expect(formatR(undefined)).toBe("—");
    expect(formatR("")).toBe("—");
  });
});

describe("toneOf", () => {
  it("associe vert, rouge et neutre au signe", () => {
    expect(toneOf("1")).toBe("positive");
    expect(toneOf("-1")).toBe("negative");
    expect(toneOf("0")).toBe("neutral");
    expect(toneOf(null)).toBe("neutral");
  });
});

describe("formatPrice", () => {
  it("retire les zéros de fin et utilise la virgule", () => {
    expect(formatPrice("1.08500000")).toBe("1,085");
    expect(formatPrice("2000.00000000")).toBe("2000");
    expect(formatPrice("65000")).toBe("65000");
    expect(formatPrice(null)).toBe("—");
  });
});
