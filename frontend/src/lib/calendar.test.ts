import { describe, expect, it } from "vitest";

import {
  currentMonth,
  dayLabel,
  daysInMonth,
  isValidMonth,
  monthGrid,
  monthLabel,
  shiftMonth,
  weekdayHeaders,
  weekdayIndex,
} from "./calendar";

describe("isValidMonth", () => {
  it.each(["2026-11", "2000-01", "2100-12"])("accepte %s", (value) => expect(isValidMonth(value)).toBe(true));
  it.each(["2026-13", "2026-00", "2026-1", "abcd", "", null, undefined, "1999-12", "2101-01", "2026-11-01"])(
    "refuse %s",
    (value) => expect(isValidMonth(value as string | null)).toBe(false),
  );
});

describe("shiftMonth", () => {
  it("avance et recule en traversant les années", () => {
    expect(shiftMonth("2026-11", 1)).toBe("2026-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-11", 0)).toBe("2026-11");
    expect(shiftMonth("2026-11", -11)).toBe("2025-12");
    expect(shiftMonth("2026-11", 14)).toBe("2028-01");
  });
});

describe("currentMonth", () => {
  it("dépend du fuseau de l'utilisateur à la frontière du mois", () => {
    const now = new Date("2026-11-30T23:30:00Z"); // déjà décembre à Paris
    expect(currentMonth("UTC", now)).toBe("2026-11");
    expect(currentMonth("Europe/Paris", now)).toBe("2026-12");
  });
});

describe("weekdayIndex / daysInMonth", () => {
  it("lundi = 0, dimanche = 6", () => {
    expect(weekdayIndex("2026-11-09")).toBe(0); // lundi
    expect(weekdayIndex("2026-11-01")).toBe(6); // dimanche
    expect(weekdayIndex("2026-11-15")).toBe(6);
    expect(weekdayIndex("2026-11-12")).toBe(3); // jeudi
  });

  it("nombre de jours, années bissextiles comprises", () => {
    expect(daysInMonth("2026-11")).toBe(30);
    expect(daysInMonth("2026-12")).toBe(31);
    expect(daysInMonth("2026-02")).toBe(28);
    expect(daysInMonth("2028-02")).toBe(29);
    expect(daysInMonth("2100-02")).toBe(28); // 2100 n'est pas bissextile
  });
});

describe("monthGrid", () => {
  it("novembre 2026 commence un dimanche : 6 semaines, lundi 26 octobre en tête", () => {
    const grid = monthGrid("2026-11");
    expect(grid).toHaveLength(6);
    expect(grid[0][0]).toBe("2026-10-26");
    expect(grid[0][6]).toBe("2026-11-01");
    expect(grid[5][0]).toBe("2026-11-30");
    expect(grid[5][6]).toBe("2026-12-06");
  });

  it("février 2027 commence un lundi et dure 28 jours : exactement 4 semaines, sans jour voisin", () => {
    const grid = monthGrid("2027-02");
    expect(grid).toHaveLength(4);
    expect(grid[0][0]).toBe("2027-02-01");
    expect(grid[3][6]).toBe("2027-02-28");
  });

  it("février 2028 (bissextile) : 5 semaines, le 29 est présent", () => {
    const grid = monthGrid("2028-02");
    expect(grid).toHaveLength(5);
    expect(grid.flat()).toContain("2028-02-29");
  });

  it.each(["2026-01", "2026-02", "2026-03", "2026-10", "2026-11", "2026-12", "2027-02", "2028-02", "2030-06"])(
    "%s : lignes de 7 jours, contiguës, lundi en premier, tous les jours du mois présents",
    (month) => {
      const grid = monthGrid(month);
      const flat = grid.flat();
      expect(grid.every((week) => week.length === 7)).toBe(true);
      expect(grid.length).toBeGreaterThanOrEqual(4);
      expect(grid.length).toBeLessThanOrEqual(6);
      expect(grid.every((week) => weekdayIndex(week[0]) === 0)).toBe(true);
      for (let i = 1; i < flat.length; i++) expect(flat[i] > flat[i - 1]).toBe(true);
      expect(flat.filter((d) => d.startsWith(month))).toHaveLength(daysInMonth(month));
      expect(flat.length).toBe(grid.length * 7);
    },
  );
});

describe("libellés", () => {
  it("mois et jour en français", () => {
    expect(monthLabel("2026-11")).toBe("novembre 2026");
    expect(monthLabel("2026-12")).toBe("décembre 2026");
    expect(dayLabel("2026-11-10")).toBe("mardi 10 novembre 2026");
  });

  it("en-têtes : lundi en premier, 7 colonnes", () => {
    const headers = weekdayHeaders();
    expect(headers).toHaveLength(7);
    expect(headers[0].long).toBe("lundi");
    expect(headers[6].long).toBe("dimanche");
    expect(headers[0].short).toMatch(/^lun/);
  });

  it("indépendants du fuseau de la machine", () => {
    const original = process.env.TZ;
    try {
      for (const zone of ["Pacific/Kiritimati", "America/Los_Angeles", "Asia/Kolkata"]) {
        process.env.TZ = zone;
        expect(dayLabel("2026-11-10"), zone).toBe("mardi 10 novembre 2026");
        expect(monthGrid("2026-11")[0][0], zone).toBe("2026-10-26");
        expect(weekdayIndex("2026-11-09"), zone).toBe(0);
      }
    } finally {
      if (original === undefined) delete process.env.TZ;
      else process.env.TZ = original;
    }
  });
});
