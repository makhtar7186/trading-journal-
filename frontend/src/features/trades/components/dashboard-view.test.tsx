import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { todayIn, shiftDate } from "@/lib/datetime";
import { OVERVIEW_A, OVERVIEW_EMPTY, queryOf, stubAnalyticsApi } from "@/test/analytics-fixtures";
import { jsonResponse, makeTrade, renderWithProviders } from "@/test/utils";
import { DashboardView } from "./dashboard-view";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/dashboard",
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

const overviewCalls = (calls: { path: string }[]) => calls.filter((c) => c.path.startsWith("/analytics/overview/"));

describe("DashboardView", () => {
  it("charge les statistiques du serveur et les affiche", async () => {
    stubAnalyticsApi();
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText("+4,5 R", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("57,14 %")).toBeInTheDocument();
    expect(screen.getByText("Répartition par résultat")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Courbe de performance cumulée/ })).toBeInTheDocument();
  });

  it("n'envoie aucune borne de date par défaut (« Tout »)", async () => {
    const { calls } = stubAnalyticsApi();
    renderWithProviders(<DashboardView />);
    await screen.findByText("57,14 %");
    const params = queryOf(overviewCalls(calls)[0].path);
    expect(params.has("date_from")).toBe(false);
    expect(params.has("date_to")).toBe(false);
  });

  it("applique les filtres de l'URL à TOUS les appels analytics (période, marché, actif, stratégie)", async () => {
    search = "range=30d&market_type=CRYPTO&asset=BTCUSD&strategy=none";
    const { calls } = stubAnalyticsApi();
    renderWithProviders(<DashboardView />);
    await screen.findByText("57,14 %");

    const today = todayIn("UTC");
    for (const prefix of ["/analytics/overview/", "/analytics/equity-curve/"]) {
      const params = queryOf(calls.find((c) => c.path.startsWith(prefix))!.path);
      expect(params.get("date_to")).toBe(today);
      expect(params.get("date_from")).toBe(shiftDate(today, -29));
      expect(params.get("market_type")).toBe("CRYPTO");
      expect(params.get("asset")).toBe("BTCUSD");
      expect(params.get("strategy")).toBe("none");
    }
  });

  it("un clic sur une période écrit l'URL (lien partageable)", async () => {
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<DashboardView />);
    await screen.findByText("57,14 %");

    await user.click(screen.getByRole("radio", { name: "7 jours" }));
    expect(replace).toHaveBeenCalledWith("/dashboard?range=7d", { scroll: false });
  });

  it("indique la période active et permet de réinitialiser", async () => {
    search = "range=90d&asset=EURUSD";
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<DashboardView />);
    await screen.findByText("57,14 %");

    expect(screen.getByRole("radio", { name: "90 jours" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("button", { name: /Réinitialiser$/ }));
    expect(replace).toHaveBeenCalledWith("/dashboard", { scroll: false });
  });

  it("journal sans trade clôturé : état vide, KPI « non défini », pas de graphiques", async () => {
    stubAnalyticsApi({ overview: OVERVIEW_EMPTY });
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText("Aucun trade clôturé pour l'instant")).toBeInTheDocument();
    expect(screen.getAllByText("Non défini").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByRole("img", { name: /Courbe/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Répartition par résultat")).not.toBeInTheDocument();
    expect(screen.getByText(/2 ouverts/)).toBeInTheDocument();
  });

  it("filtres sans résultat : message distinct et bouton pour les réinitialiser", async () => {
    search = "range=7d";
    stubAnalyticsApi({ overview: OVERVIEW_EMPTY });
    const user = userEvent.setup();
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText("Aucun trade clôturé pour ces filtres")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(replace).toHaveBeenCalledWith("/dashboard", { scroll: false });
  });

  it("erreur serveur : message et bouton Réessayer qui relance la requête", async () => {
    let attempts = 0;
    stubAnalyticsApi({}, (call) => {
      if (!call.path.startsWith("/analytics/overview/")) return undefined;
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, 500) : undefined;
    });
    const user = userEvent.setup();
    renderWithProviders(<DashboardView />);

    const alert = await screen.findByText("Impossible de charger les statistiques.");
    expect(alert).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Réessayer" })[0]);
    expect(await screen.findByText("57,14 %")).toBeInTheDocument();
  });

  it("les derniers trades ne dépendent pas des filtres de période", async () => {
    search = "range=7d";
    const { calls } = stubAnalyticsApi({}, (call) =>
      call.path.startsWith("/trades/")
        ? jsonResponse({ count: 1, next: null, previous: null, results: [makeTrade({ name: "Ancien trade" })] })
        : undefined,
    );
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText("Ancien trade")).toBeInTheDocument();
    const tradesCall = calls.find((c) => c.path.startsWith("/trades/"))!;
    expect(queryOf(tradesCall.path).has("date_from")).toBe(false);
  });

  it("ne recalcule rien côté client : affiche la valeur du serveur même inattendue", async () => {
    stubAnalyticsApi({ overview: { ...OVERVIEW_A, win_rate: "12.34", total_r: "99.0000" } });
    renderWithProviders(<DashboardView />);
    expect(await screen.findByText("12,34 %")).toBeInTheDocument();
    expect(screen.getByText("+99 R", { selector: "p" })).toBeInTheDocument();
  });
});

// utilitaire pour éviter un avertissement d'import inutilisé si un test est retiré
void waitFor;
void within;
