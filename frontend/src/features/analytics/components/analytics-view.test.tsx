import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OVERVIEW_EMPTY, PERFORMANCE_A, queryOf, stubAnalyticsApi } from "@/test/analytics-fixtures";
import { renderWithProviders } from "@/test/utils";
import { AnalyticsView } from "./analytics-view";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/analytics",
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  search = "";
  replace.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("AnalyticsView", () => {
  it("affiche les sections : indicateurs, performance, période, actif, marché, stratégie", async () => {
    stubAnalyticsApi();
    renderWithProviders(<AnalyticsView />);

    expect(await screen.findByText("57,14 %")).toBeInTheDocument();
    expect(await screen.findByText("Gain moyen")).toBeInTheDocument();
    expect(screen.getByText("Résultat par période")).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: "Résultats par actif" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Résultats par marché" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Résultats par stratégie" })).toBeInTheDocument();
  });

  it("interroge les trois regroupements et la performance avec les filtres de l'URL", async () => {
    search = "market_type=FOREX&asset=EURUSD";
    const { calls } = stubAnalyticsApi();
    renderWithProviders(<AnalyticsView />);
    await screen.findByRole("table", { name: "Résultats par stratégie" });

    for (const endpoint of ["performance", "by-asset", "by-market", "by-strategy", "by-period", "overview"]) {
      // by-asset est aussi interrogé SANS filtre par le sélecteur d'actifs : on ne regarde que les appels filtrés.
      const filtered = calls.filter((c) => c.path.startsWith(`/analytics/${endpoint}/`) && queryOf(c.path).has("market_type"));
      expect(filtered.length, endpoint).toBeGreaterThan(0);
      for (const call of filtered) expect(queryOf(call.path).get("asset")).toBe("EURUSD");
      // et aucune requête analytics n'ignore le filtre marché, hors sélecteur d'actifs
      const unfiltered = calls.filter((c) => c.path.startsWith(`/analytics/${endpoint}/`) && !queryOf(c.path).has("market_type"));
      expect(unfiltered.length === 0 || endpoint === "by-asset", endpoint).toBe(true);
    }
  });

  it("changer la granularité relance by-period avec la nouvelle valeur", async () => {
    const { calls } = stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<AnalyticsView />);
    await screen.findByRole("button", { name: "Semaine" });

    expect(queryOf(calls.find((c) => c.path.startsWith("/analytics/by-period/"))!.path).get("granularity")).toBe("month");
    await user.click(screen.getByRole("button", { name: "Semaine" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.startsWith("/analytics/by-period/") && queryOf(c.path).get("granularity") === "week")).toBe(true),
    );
  });

  it("aucun trade clôturé : état vide, aucune section de détail", async () => {
    stubAnalyticsApi({ overview: OVERVIEW_EMPTY });
    renderWithProviders(<AnalyticsView />);

    expect(await screen.findByText("Aucun trade clôturé pour l'instant")).toBeInTheDocument();
    expect(screen.queryByText("Résultat par période")).not.toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Résultats par actif" })).not.toBeInTheDocument();
  });

  it("les trades ouverts sont rappelés comme exclus", async () => {
    stubAnalyticsApi();
    renderWithProviders(<AnalyticsView />);
    expect(await screen.findByText(/1 ouvert .*exclus des statistiques/)).toBeInTheDocument();
  });

  it("performance sans perte : pire trade « non défini »", async () => {
    stubAnalyticsApi({
      performance: { ...PERFORMANCE_A, worst_trade: null, average_loss_r: null, gross_loss_r: null },
    });
    renderWithProviders(<AnalyticsView />);
    expect((await screen.findAllByText("Aucun trade perdant.", { selector: "p" })).length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Pire trade")).toBeInTheDocument();
  });
});
