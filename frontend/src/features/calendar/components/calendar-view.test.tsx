import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CALENDAR_EMPTY, queryOf, stubAnalyticsApi } from "@/test/analytics-fixtures";
import { jsonResponse, renderWithProviders } from "@/test/utils";
import { CalendarView } from "./calendar-view";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/calendar",
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
  search = "month=2026-11";
  replace.mockReset();
  // Seule la date est simulée (les minuteries restent réelles pour React Query et user-event).
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-15T10:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const calendarCalls = (calls: { path: string }[]) => calls.filter((c) => c.path.startsWith("/analytics/calendar/"));

describe("CalendarView — données et résumé", () => {
  it("affiche le mois, ses totaux et la grille", async () => {
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);

    expect(await screen.findByRole("heading", { name: "novembre 2026" })).toBeInTheDocument();
    expect(await screen.findByText("+0,5 R", { selector: "p" })).toBeInTheDocument(); // résultat du mois
    expect(screen.getByText("1 G · 2 P · 0 BE")).toBeInTheDocument();
    expect(screen.getByText(/dont 1 trade ouvert/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /mardi 10 novembre : \+2 R/ })).toBeInTheDocument();
  });

  it("demande le mois de l'URL avec ses filtres", async () => {
    search = "month=2026-11&market_type=CRYPTO&strategy=none";
    const { calls } = stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");

    const params = queryOf(calendarCalls(calls)[0].path);
    expect(params.get("month")).toBe("2026-11");
    expect(params.get("market_type")).toBe("CRYPTO");
    expect(params.get("strategy")).toBe("none");
  });

  it("mois par défaut = mois courant de l'utilisateur ; mois invalide ignoré", async () => {
    search = "month=n-importe-quoi";
    const { calls } = stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    expect(await screen.findByRole("heading", { name: "novembre 2026" })).toBeInTheDocument();
    expect(queryOf(calendarCalls(calls)[0].path).get("month")).toBe("2026-11");
  });

  it("mois sans trade : message explicite, résultat « non défini » (pas 0)", async () => {
    stubAnalyticsApi({ calendar: CALENDAR_EMPTY });
    renderWithProviders(<CalendarView />);

    expect(await screen.findByText("Aucun trade ce mois-ci.")).toBeInTheDocument();
    expect(screen.getByText("Non défini")).toBeInTheDocument();
    expect(screen.getByText("Aucun trade clôturé ce mois-ci.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /aucun trade/ })).toHaveLength(30);
  });

  it("mois vide avec filtres : message adapté", async () => {
    search = "month=2026-11&market_type=CRYPTO";
    stubAnalyticsApi({ calendar: CALENDAR_EMPTY });
    renderWithProviders(<CalendarView />);
    expect(await screen.findByText("Aucun trade ce mois-ci pour ces filtres.")).toBeInTheDocument();
  });

  it("erreur serveur : message et bouton Réessayer", async () => {
    let attempts = 0;
    stubAnalyticsApi({}, (call) => {
      if (!call.path.startsWith("/analytics/calendar/")) return undefined;
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, 500) : undefined;
    });
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);

    expect(await screen.findByText("Impossible de charger le calendrier.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByRole("grid")).toBeInTheDocument();
  });
});

describe("CalendarView — navigation (état dans l'URL)", () => {
  it("mois précédent / suivant écrivent le mois et effacent le jour sélectionné", async () => {
    search = "month=2026-11&day=2026-11-10";
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");

    await user.click(screen.getByRole("button", { name: "Mois précédent" }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?month=2026-10", { scroll: false });
    await user.click(screen.getByRole("button", { name: "Mois suivant" }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?month=2026-12", { scroll: false });
  });

  it("traverse le changement d'année", async () => {
    search = "month=2026-12";
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");
    await user.click(screen.getByRole("button", { name: "Mois suivant" }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?month=2027-01", { scroll: false });
  });

  it("« Aujourd'hui » : désactivé sur le mois courant ; ailleurs, revient au mois courant avec le jour", async () => {
    stubAnalyticsApi();
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");
    expect(screen.getByRole("button", { name: "Aujourd'hui" })).toBeDisabled();
    unmount();

    search = "month=2026-03";
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");
    await user.click(screen.getByRole("button", { name: "Aujourd'hui" }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?day=2026-11-15", { scroll: false }); // mois courant = défaut, non écrit
  });

  it("un clic sur un jour l'écrit dans l'URL", async () => {
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);
    await user.click(await screen.findByRole("button", { name: /mardi 10 novembre/ }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?day=2026-11-10", { scroll: false });
  });

  it("conserve les filtres en changeant de mois", async () => {
    search = "month=2026-11&market_type=FOREX";
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");
    await user.click(screen.getByRole("button", { name: "Mois suivant" }));
    expect(replace).toHaveBeenLastCalledWith("/calendar?month=2026-12&market_type=FOREX", { scroll: false });
  });

  it("changer de filtre le range dans l'URL ; Réinitialiser les retire", async () => {
    search = "month=2026-11&market_type=FOREX";
    stubAnalyticsApi();
    const user = userEvent.setup();
    renderWithProviders(<CalendarView />);
    await screen.findByRole("grid");

    await user.click(screen.getByRole("button", { name: /Réinitialiser/ }));
    expect(replace).toHaveBeenLastCalledWith("/calendar", { scroll: false }); // le mois courant est la valeur par défaut
  });
});

describe("CalendarView — détail du jour", () => {
  it("sans jour sélectionné : invite à en choisir un", async () => {
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    expect(await screen.findByText(/Sélectionnez un jour/)).toBeInTheDocument();
  });

  it("liste les trades du jour avec lien, statut, RR et heure", async () => {
    search = "month=2026-11&day=2026-11-10";
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);

    expect(await screen.findByRole("heading", { name: /mardi 10 novembre 2026/ })).toBeInTheDocument();
    const panel = screen.getByText("Résultat du jour").closest('[data-slot="card"]') as HTMLElement;
    expect(within(panel).getByText("+2 R", { selector: "span" })).toBeInTheDocument();
    expect(within(panel).getByText(/1 gagnant, 1 perdant, 0 break-even/)).toBeInTheDocument();

    const win = within(panel).getByRole("link", { name: /Breakout matin/ });
    expect(win).toHaveAttribute("href", "/trades/c1");
    expect(win).toHaveTextContent("Gagnant");
    expect(win).toHaveTextContent("+3 R");
    expect(win).toHaveTextContent("clôturé à 09:30");
    expect(within(panel).getByRole("link", { name: /Retournement/ })).toHaveTextContent("−1 R");
  });

  it("jour avec seulement un trade ouvert : résultat non défini, trade sans RR", async () => {
    search = "month=2026-11&day=2026-11-12";
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);

    const panel = (await screen.findByText("Résultat du jour")).closest('[data-slot="card"]') as HTMLElement;
    expect(within(panel).getByText("Non défini")).toBeInTheDocument();
    expect(within(panel).getByText(/résultat non défini/)).toBeInTheDocument();
    expect(within(panel).getByText(/1 trade ouvert pris ce jour-là/)).toBeInTheDocument();
    const link = within(panel).getByRole("link", { name: /Trade en cours/ });
    expect(link).toHaveTextContent("Ouvert");
    expect(link).toHaveTextContent("pris à 08:00");
    expect(link).toHaveTextContent("—");
  });

  it("jour sans trade", async () => {
    search = "month=2026-11&day=2026-11-03";
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    expect(await screen.findByText("Aucun trade ce jour-là.")).toBeInTheDocument();
  });

  it("ignore un jour qui n'appartient pas au mois affiché", async () => {
    search = "month=2026-11&day=2026-10-10";
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    expect(await screen.findByText(/Sélectionnez un jour/)).toBeInTheDocument();
    expect(screen.queryAllByRole("button", { pressed: true })).toHaveLength(0);
  });

  it("le jour sélectionné est signalé dans la grille", async () => {
    search = "month=2026-11&day=2026-11-20";
    stubAnalyticsApi();
    renderWithProviders(<CalendarView />);
    expect(await screen.findByRole("button", { name: /vendredi 20 novembre/ })).toHaveAttribute("aria-pressed", "true");
  });
});

