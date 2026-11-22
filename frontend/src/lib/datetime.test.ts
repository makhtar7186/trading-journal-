import { describe, expect, it } from "vitest";

import { formatDateTime, isoToZonedInput, isValidTimeZone, shiftDate, startOfYear, todayIn, zonedInputToIso } from "./datetime";

describe("todayIn / shiftDate / startOfYear", () => {
  const now = new Date("2026-11-15T23:30:00Z");

  it("le jour courant dépend du fuseau", () => {
    expect(todayIn("UTC", now)).toBe("2026-11-15");
    expect(todayIn("Europe/Paris", now)).toBe("2026-11-16");
    expect(todayIn("America/Los_Angeles", now)).toBe("2026-11-15");
    expect(todayIn("Mars/Olympus", now)).toBe("2026-11-15"); // repli UTC
  });

  it("shiftDate traverse mois, années et années bissextiles", () => {
    expect(shiftDate("2026-03-01", -1)).toBe("2026-02-28");
    expect(shiftDate("2028-03-01", -1)).toBe("2028-02-29");
    expect(shiftDate("2026-12-31", 1)).toBe("2027-01-01");
    expect(shiftDate("2026-01-01", -1)).toBe("2025-12-31");
    expect(shiftDate("2026-11-15", 0)).toBe("2026-11-15");
    expect(shiftDate("2026-11-15", -29)).toBe("2026-10-17");
  });

  it("shiftDate n'est pas affecté par le changement d'heure", () => {
    expect(shiftDate("2026-10-24", 2)).toBe("2026-10-26"); // fin de l'heure d'été en Europe : 25 h
    expect(shiftDate("2026-03-28", 2)).toBe("2026-03-30");
  });

  it("shiftDate donne le même résultat quel que soit le fuseau de la machine", () => {
    const original = process.env.TZ;
    try {
      for (const zone of ["Pacific/Kiritimati", "Pacific/Pago_Pago", "America/Los_Angeles", "Europe/Paris", "Asia/Kolkata", "UTC"]) {
        process.env.TZ = zone;
        expect(shiftDate("2026-03-29", 1), zone).toBe("2026-03-30"); // jour de changement d'heure en Europe
        expect(shiftDate("2026-11-15", -29), zone).toBe("2026-10-17");
        expect(shiftDate("2026-01-01", -1), zone).toBe("2025-12-31");
      }
    } finally {
      if (original === undefined) delete process.env.TZ;
      else process.env.TZ = original;
    }
  });

  it("début d'année", () => {
    expect(startOfYear("2026-11-15")).toBe("2026-01-01");
  });
});

describe("zonedInputToIso", () => {
  it("UTC : identité", () => {
    expect(zonedInputToIso("2026-11-10T09:30", "UTC")).toBe("2026-11-10T09:30:00.000Z");
  });

  it("Paris en hiver (UTC+1)", () => {
    expect(zonedInputToIso("2026-11-10T09:30", "Europe/Paris")).toBe("2026-11-10T08:30:00.000Z");
  });

  it("Paris en été (UTC+2) : tient compte de l'heure d'été", () => {
    expect(zonedInputToIso("2026-07-10T09:30", "Europe/Paris")).toBe("2026-07-10T07:30:00.000Z");
  });

  it("New York (UTC−5 en hiver)", () => {
    expect(zonedInputToIso("2026-11-10T09:30", "America/New_York")).toBe("2026-11-10T14:30:00.000Z");
  });

  it("Dakar = UTC", () => {
    expect(zonedInputToIso("2026-11-10T09:30", "Africa/Dakar")).toBe("2026-11-10T09:30:00.000Z");
  });

  it("repli sur UTC si le fuseau est inconnu", () => {
    expect(zonedInputToIso("2026-11-10T09:30", "Mars/Olympus")).toBe("2026-11-10T09:30:00.000Z");
  });

  it("retourne null pour une saisie invalide", () => {
    expect(zonedInputToIso("", "UTC")).toBeNull();
    expect(zonedInputToIso("10/11/2026", "UTC")).toBeNull();
  });
});

describe("isoToZonedInput", () => {
  it("affiche l'heure murale du fuseau", () => {
    expect(isoToZonedInput("2026-11-10T08:30:00Z", "Europe/Paris")).toBe("2026-11-10T09:30");
    expect(isoToZonedInput("2026-07-10T07:30:00Z", "Europe/Paris")).toBe("2026-07-10T09:30");
  });

  it("minuit s'affiche 00:00 (pas 24:00)", () => {
    expect(isoToZonedInput("2026-11-10T00:00:00Z", "UTC")).toBe("2026-11-10T00:00");
  });

  it("aller-retour sans dérive", () => {
    for (const tz of ["UTC", "Europe/Paris", "America/New_York", "Asia/Tokyo", "Australia/Sydney"]) {
      const iso = zonedInputToIso("2026-03-15T14:45", tz);
      expect(iso).not.toBeNull();
      expect(isoToZonedInput(iso as string, tz)).toBe("2026-03-15T14:45");
    }
  });

  it("chaîne vide si la date est invalide", () => {
    expect(isoToZonedInput("pas-une-date", "UTC")).toBe("");
  });
});

describe("formatDateTime / isValidTimeZone", () => {
  it("tiret si absente", () => {
    expect(formatDateTime(null, "UTC")).toBe("—");
  });

  it("formate dans le fuseau demandé", () => {
    const paris = formatDateTime("2026-11-10T23:30:00Z", "Europe/Paris");
    expect(paris).toContain("11 nov. 2026"); // déjà le lendemain à Paris
  });

  it("valide les fuseaux", () => {
    expect(isValidTimeZone("Europe/Paris")).toBe(true);
    expect(isValidTimeZone("Mars/Olympus")).toBe(false);
  });
});
