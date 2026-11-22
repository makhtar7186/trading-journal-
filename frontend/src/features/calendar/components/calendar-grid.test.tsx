import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CALENDAR_A } from "@/test/analytics-fixtures";
import { CalendarGrid } from "./calendar-grid";

const noop = () => {};

function renderGrid(props: Partial<React.ComponentProps<typeof CalendarGrid>> = {}) {
  return render(
    <CalendarGrid month="2026-11" days={CALENDAR_A.days} selectedDay={null} today="2026-11-15" onSelectDay={noop} onMonthChange={noop} {...props} />,
  );
}

const day = (label: RegExp) => screen.getByRole("button", { name: label });

/** Grille pilotée comme dans l'application : le mois change quand la grille le demande. */
function Controlled({ start = "2026-11" }: { start?: string }) {
  const [month, setMonth] = useState(start);
  return <CalendarGrid month={month} days={[]} selectedDay={null} today="2026-11-15" onSelectDay={noop} onMonthChange={setMonth} />;
}

describe("CalendarGrid — structure", () => {
  it("lundi en premier, 6 semaines pour novembre 2026, jours du mois voisin non interactifs", () => {
    renderGrid();
    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((h) => h.getAttribute("aria-label"))).toEqual(["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]);
    expect(screen.getAllByRole("row")).toHaveLength(7); // en-tête + 6 semaines
    expect(screen.getAllByRole("button")).toHaveLength(30); // seulement les 30 jours de novembre

    const outside = screen.getAllByRole("gridcell").filter((c) => c.getAttribute("aria-disabled") === "true");
    expect(outside).toHaveLength(12); // 6 jours d'octobre + 6 de décembre
    expect(within(outside[0]).queryByRole("button")).not.toBeInTheDocument();
  });

  it("libellé accessible complet : date, résultat signé, nombre de trades", () => {
    renderGrid();
    expect(day(/mardi 10 novembre : \+2 R, 2 trades clôturés/)).toBeInTheDocument();
    expect(day(/vendredi 20 novembre : −1,5 R, 1 trade clôturé/)).toBeInTheDocument();
  });

  it("jour avec seulement un trade ouvert : « ouvert », jamais de résultat à 0", () => {
    renderGrid();
    const open = day(/jeudi 12 novembre/);
    expect(open).toHaveAccessibleName("jeudi 12 novembre : 1 ouvert");
    expect(open).not.toHaveTextContent(/R|\+|−/);
    expect(open).toHaveTextContent("● 1");
  });

  it("jour sans trade", () => {
    renderGrid();
    expect(day(/lundi 2 novembre/)).toHaveAccessibleName("lundi 2 novembre : aucun trade");
  });

  it("résultat écrit avec son signe dans la cellule (pas la couleur seule)", () => {
    renderGrid();
    expect(day(/mardi 10 novembre/)).toHaveTextContent("+2");
    expect(day(/vendredi 20 novembre/)).toHaveTextContent("−1,5");
  });

  it("un jour de break-even affiche 0, pas un tiret", () => {
    const flat = { ...CALENDAR_A.days[0], date: "2026-11-05", total_r: "0.0000", wins: 0, losses: 0, break_even: 2, trades: [] };
    renderGrid({ days: [flat] });
    expect(day(/jeudi 5 novembre : 0 R/)).toHaveTextContent("0");
  });

  it("marque aujourd'hui et le jour sélectionné", () => {
    renderGrid({ selectedDay: "2026-11-10" });
    expect(day(/dimanche 15 novembre/)).toHaveAttribute("aria-current", "date");
    expect(day(/mardi 10 novembre/)).toHaveAttribute("aria-pressed", "true");
    expect(day(/mercredi 11 novembre/)).toHaveAttribute("aria-pressed", "false");
  });

  it("un clic sélectionne le jour", async () => {
    const onSelectDay = vi.fn();
    renderGrid({ onSelectDay });
    await userEvent.setup().click(day(/mardi 10 novembre/));
    expect(onSelectDay).toHaveBeenCalledWith("2026-11-10");
  });
});

describe("CalendarGrid — clavier (tabulation itinérante)", () => {
  const tabStops = () => screen.getAllByRole("button").filter((b) => b.tabIndex === 0);

  it("un seul arrêt de tabulation : aujourd'hui, sinon le jour sélectionné, sinon le 1er", () => {
    const { unmount } = renderGrid();
    expect(tabStops()).toEqual([day(/dimanche 15 novembre/)]);
    unmount();
    renderGrid({ selectedDay: "2026-11-10" });
    expect(tabStops()).toEqual([day(/mardi 10 novembre/)]);
  });

  it("hors du mois affiché, l'arrêt de tabulation est le 1er du mois", () => {
    renderGrid({ today: "2026-12-25" });
    expect(tabStops()).toEqual([day(/dimanche 1 novembre/)]);
  });

  it("flèches : ±1 jour, ±7 jours ; Début/Fin : début et fin de semaine", async () => {
    const user = userEvent.setup();
    renderGrid();
    day(/dimanche 15 novembre/).focus();

    await user.keyboard("{ArrowLeft}");
    expect(day(/samedi 14 novembre/)).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(day(/samedi 21 novembre/)).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(day(/samedi 7 novembre/)).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(day(/dimanche 8 novembre/)).toHaveFocus();
    await user.keyboard("{Home}");
    expect(day(/lundi 2 novembre/)).toHaveFocus(); // semaine du 2 au 8
    await user.keyboard("{End}");
    expect(day(/dimanche 8 novembre/)).toHaveFocus();
  });

  it("l'arrêt de tabulation suit le focus", async () => {
    const user = userEvent.setup();
    renderGrid();
    day(/dimanche 15 novembre/).focus();
    await user.keyboard("{ArrowRight}");
    expect(tabStops()).toEqual([day(/lundi 16 novembre/)]);
  });

  it("Entrée sélectionne le jour focalisé", async () => {
    const onSelectDay = vi.fn();
    const user = userEvent.setup();
    renderGrid({ onSelectDay });
    day(/mardi 10 novembre/).focus();
    await user.keyboard("{Enter}");
    expect(onSelectDay).toHaveBeenCalledWith("2026-11-10");
  });

  it("sortir du mois par les flèches demande le mois voisin et y place le focus", async () => {
    const user = userEvent.setup();
    render(<Controlled />);
    day(/lundi 30 novembre/).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-label", expect.stringContaining("2026-12"));
    expect(day(/mardi 1 décembre/)).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-label", expect.stringContaining("2026-11"));
    expect(day(/lundi 30 novembre/)).toHaveFocus();
  });

  it("PageBas / PageHaut changent de mois en gardant le même jour ; calés sur la fin du mois d'arrivée", async () => {
    const user = userEvent.setup();
    render(<Controlled start="2027-01" />);
    day(/dimanche 31 janvier/).focus();
    await user.keyboard("{PageDown}");
    expect(day(/dimanche 28 février/)).toHaveFocus(); // 31 janv. → 28 févr. (pas un jour inexistant)
    await user.keyboard("{PageUp}");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-label", expect.stringContaining("2027-01"));
    expect(day(/jeudi 28 janvier/)).toHaveFocus(); // le 28 est conservé en revenant
  });
});
