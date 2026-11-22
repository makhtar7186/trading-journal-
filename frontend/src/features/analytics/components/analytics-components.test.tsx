import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EQUITY_A, GROUPS_A, OVERVIEW_A, OVERVIEW_EMPTY, PERFORMANCE_A, PERIODS_A } from "@/test/analytics-fixtures";
import { renderWithProviders, stubApi } from "@/test/utils";
import type { Overview, Performance } from "@/types/api";
import { DistributionBar } from "./distribution-bar";
import { EquityChart } from "./equity-chart";
import { GroupsTable } from "./groups-table";
import { OverviewKpis } from "./overview-kpis";
import { PerformancePanel } from "./performance-panel";
import { PeriodChart, periodLabel } from "./period-chart";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => vi.unstubAllGlobals());

const tile = (label: string) => screen.getByText(label).closest('[data-slot="card"]') as HTMLElement;

describe("OverviewKpis", () => {
  it("affiche les valeurs du serveur, formatées (signe, virgule, unités)", () => {
    render(<OverviewKpis overview={OVERVIEW_A} />);
    expect(within(tile("Performance cumulée")).getByText("+4,5 R")).toBeInTheDocument();
    expect(within(tile("Win rate")).getByText("57,14 %")).toBeInTheDocument();
    expect(within(tile("Expectancy")).getByText("+0,5625 R")).toBeInTheDocument();
    expect(within(tile("Profit factor")).getByText("2,5")).toBeInTheDocument();
    expect(within(tile("Trades clôturés")).getByText("8")).toBeInTheDocument();
    expect(within(tile("Trades clôturés")).getByText(/1 ouvert .*exclus/)).toBeInTheDocument();
  });

  it("aucun trade clôturé : « Non défini » partout, jamais 0, avec la raison", () => {
    render(<OverviewKpis overview={OVERVIEW_EMPTY} />);
    for (const label of ["Performance cumulée", "Win rate", "Expectancy", "Profit factor"]) {
      expect(within(tile(label)).getByText("Non défini")).toBeInTheDocument();
      expect(within(tile(label)).getByText("Aucun trade clôturé.")).toBeInTheDocument();
    }
    expect(within(tile("Trades clôturés")).getByText("0")).toBeInTheDocument();
    expect(screen.queryByText("0 R")).not.toBeInTheDocument();
    expect(screen.queryByText("0 %")).not.toBeInTheDocument();
  });

  it("sans perte : le profit factor est « non défini », pas infini ni 0", () => {
    const overview: Overview = { ...OVERVIEW_A, losses: 0, profit_factor: null, win_rate: "100.00" };
    render(<OverviewKpis overview={overview} />);
    expect(within(tile("Profit factor")).getByText("Non défini")).toBeInTheDocument();
    expect(within(tile("Profit factor")).getByText("Aucune perte : ratio non défini.")).toBeInTheDocument();
    expect(within(tile("Profit factor")).queryByText(/∞|Infinity/)).not.toBeInTheDocument();
    expect(within(tile("Win rate")).getByText("100 %")).toBeInTheDocument();
  });

  it("uniquement des break-even : win rate non défini mais expectancy définie (0 R)", () => {
    const overview: Overview = { ...OVERVIEW_A, wins: 0, losses: 0, break_even: 3, closed_trades: 3, win_rate: null, profit_factor: null, expectancy_r: "0.0000", total_r: "0.0000" };
    render(<OverviewKpis overview={overview} />);
    expect(within(tile("Win rate")).getByText("Aucun trade gagnant ni perdant.")).toBeInTheDocument();
    expect(within(tile("Expectancy")).getByText("0 R")).toBeInTheDocument();
  });

  it("couleur selon le signe + signe explicite (jamais la couleur seule)", () => {
    render(<OverviewKpis overview={{ ...OVERVIEW_A, total_r: "-2.0000", expectancy_r: "-0.2500" }} />);
    const total = within(tile("Performance cumulée")).getByText("−2 R");
    expect(total).toHaveClass("text-negative");
    expect(within(tile("Expectancy")).getByText("−0,25 R")).toHaveClass("text-negative");
  });
});

describe("DistributionBar", () => {
  it("décrit la répartition pour les lecteurs d'écran et dans la légende", () => {
    render(<DistributionBar wins={4} losses={3} breakEven={1} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "aria-label",
      "Répartition des 8 trades clôturés : 4 gagnants, 3 perdants, 1 break-even",
    );
    const legend = screen.getByRole("list");
    expect(within(legend).getByText("Gagnants").parentElement).toHaveTextContent("4");
    expect(within(legend).getByText("Break-even").parentElement).toHaveTextContent("(13 %)");
  });

  it("ne dessine pas de segment pour un état à zéro", () => {
    render(<DistributionBar wins={2} losses={0} breakEven={0} />);
    expect(screen.getByRole("img").children).toHaveLength(1);
  });

  it("n'imprime pas de nombre dans un segment trop étroit (jamais de texte rogné)", () => {
    render(<DistributionBar wins={95} losses={4} breakEven={1} />);
    const segments = Array.from(screen.getByRole("img").children);
    expect(segments).toHaveLength(3);
    expect(segments[0]).toHaveTextContent("95");
    expect(segments[2]).toBeEmptyDOMElement(); // 1 % : l'info reste dans la légende et l'infobulle
    expect(segments[2]).toHaveAttribute("title", "Break-even : 1 (1 %)");
  });

  it("ne plante pas sans aucun trade", () => {
    render(<DistributionBar wins={0} losses={0} breakEven={0} />);
    expect(screen.getByRole("img").children).toHaveLength(0);
  });
});

describe("GroupsTable", () => {
  it("affiche chaque groupe ; PF non défini en toutes lettres", () => {
    render(<GroupsTable title="Résultats par actif" firstColumn="Actif" groups={GROUPS_A} />);
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3); // en-tête + 2 groupes
    const btc = within(screen.getByRole("row", { name: /BTCUSD/ }));
    expect(btc.getByText("100 %")).toBeInTheDocument();
    expect(btc.getByText("Non défini")).toBeInTheDocument(); // aucune perte
    expect(btc.getAllByText("+1,5 R", { selector: "span" })).toHaveLength(2); // expectancy et total
  });

  it("états vide et chargement", () => {
    const { rerender } = render(<GroupsTable title="T" firstColumn="Actif" groups={[]} />);
    expect(screen.getByText(/Aucun trade clôturé pour ces filtres/)).toBeInTheDocument();
    rerender(<GroupsTable title="T" firstColumn="Actif" groups={undefined} loading />);
    expect(screen.getByText("Chargement…")).toBeInTheDocument();
  });
});

describe("PerformancePanel", () => {
  beforeEach(() => {
    stubApi();
  });

  it("affiche gain/perte moyens signés, extrêmes et séries", async () => {
    renderWithProviders(<PerformancePanel performance={PERFORMANCE_A} />);
    expect(within(tile("Gain moyen")).getByText("+1,875 R")).toBeInTheDocument();
    expect(within(tile("Perte moyenne")).getByText("−1 R")).toBeInTheDocument();
    expect(within(tile("Perte moyenne")).getByText("Valeur signée (négative)")).toBeInTheDocument();
    expect(await within(tile("Meilleur trade")).findByRole("link", { name: "XAUUSD setup 2" })).toHaveAttribute("href", "/trades/b");
    expect(screen.getByText("gains d'affilée (max)").previousElementSibling).toHaveTextContent("3");
    expect(screen.getByText("pertes d'affilée (max)").previousElementSibling).toHaveTextContent("2");
    expect(screen.getByText("1 perte")).toBeInTheDocument();
    expect(screen.getByText(/break-even ignorés/)).toBeInTheDocument();
  });

  it("sans gain ni perte : « Non défini » avec la raison, aucune série", () => {
    const empty: Performance = {
      gross_profit_r: null,
      gross_loss_r: null,
      average_win_r: null,
      average_loss_r: null,
      best_trade: null,
      worst_trade: null,
      streaks: { max_win: 0, max_loss: 0, current_type: null, current_length: 0 },
    };
    renderWithProviders(<PerformancePanel performance={empty} />);
    expect(within(tile("Meilleur trade")).getByText("Aucun trade gagnant.")).toBeInTheDocument();
    expect(within(tile("Pire trade")).getByText("Aucun trade perdant.")).toBeInTheDocument();
    expect(within(tile("Gain moyen")).getByText("Non défini")).toBeInTheDocument();
    expect(screen.getByText("série en cours").previousElementSibling).toHaveTextContent("—");
  });

  it("pluralise la série en cours", () => {
    renderWithProviders(<PerformancePanel performance={{ ...PERFORMANCE_A, streaks: { max_win: 4, max_loss: 1, current_type: "WIN", current_length: 4 } }} />);
    expect(screen.getByText("4 gains")).toBeInTheDocument();
  });
});

describe("EquityChart", () => {
  it("décrit la courbe et fournit le tableau de données exact (valeurs du serveur)", () => {
    renderWithProviders(<EquityChart points={EQUITY_A.points} totalR={EQUITY_A.total_r} />);
    expect(screen.getByRole("img", { name: /Courbe de performance cumulée sur 3 trades, total \+4 R/ })).toBeInTheDocument();

    const rows = within(screen.getByRole("table", { hidden: true })).getAllByRole("row", { hidden: true });
    expect(rows).toHaveLength(4);
    expect(rows[2]).toHaveTextContent("Deuxième");
    expect(rows[2]).toHaveTextContent("+3 R");
    expect(rows[2]).toHaveTextContent("+5 R"); // cumul
    expect(rows[3]).toHaveTextContent("−1 R");
    expect(rows[3]).toHaveTextContent("+4 R");
  });
});

describe("PeriodChart", () => {
  it("libellés de période selon la granularité", () => {
    expect(periodLabel("2026-11", "month")).toMatch(/nov\.? 2026/);
    expect(periodLabel("2026-11-09", "day")).toMatch(/9 nov/);
    expect(periodLabel("2026-11-09", "week")).toMatch(/sem\. du 9 nov/);
  });

  it("bascule de granularité : le bouton actif est signalé, le clic notifie le parent", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<PeriodChart periods={PERIODS_A} granularity="month" onGranularityChange={onChange} />);

    expect(screen.getByRole("button", { name: "Mois" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Semaine" })).toHaveAttribute("aria-pressed", "false");
    await user.click(screen.getByRole("button", { name: "Semaine" }));
    expect(onChange).toHaveBeenCalledWith("week");
  });

  it("tableau de données : résultat, win rate non défini en toutes lettres", () => {
    const periods = [{ ...PERIODS_A[0], win_rate: null }, PERIODS_A[1]];
    renderWithProviders(<PeriodChart periods={periods} granularity="month" onGranularityChange={() => {}} />);
    const rows = within(screen.getByRole("table", { hidden: true })).getAllByRole("row", { hidden: true });
    expect(rows).toHaveLength(3);
    expect(rows[1]).toHaveTextContent("Non défini");
    expect(rows[1]).toHaveTextContent("−1 R");
    expect(rows[2]).toHaveTextContent("+3 R");
  });
});
