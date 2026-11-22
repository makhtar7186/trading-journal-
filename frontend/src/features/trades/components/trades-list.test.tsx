import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, makeTrade, renderWithProviders, stubApi } from "@/test/utils";
import { TradesList } from "./trades-list";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/trades",
  useSearchParams: () => new URLSearchParams(search),
}));

const page = (results: ReturnType<typeof makeTrade>[], count = results.length) =>
  jsonResponse({ count, next: null, previous: null, results });

beforeEach(() => {
  search = "";
  replace.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe("TradesList — états", () => {
  it("affiche un état de chargement puis les trades", async () => {
    stubApi((c) => (c.path.startsWith("/trades/") ? page([makeTrade({ name: "Mon trade" })]) : undefined));
    renderWithProviders(<TradesList />);

    expect(screen.getByRole("status", { name: /Chargement/ })).toBeInTheDocument();
    expect((await screen.findAllByText("Mon trade")).length).toBeGreaterThan(0);
  });

  it("journal vide : invite à ajouter un premier trade", async () => {
    stubApi((c) => (c.path.startsWith("/trades/") ? page([]) : undefined));
    renderWithProviders(<TradesList />);

    expect(await screen.findByText("Votre journal est vide")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ajouter un trade/ })).toHaveAttribute("href", "/trades/new");
  });

  it("aucun résultat avec filtres : message distinct du journal vide", async () => {
    search = "status=WIN";
    stubApi((c) => (c.path.startsWith("/trades/") ? page([]) : undefined));
    renderWithProviders(<TradesList />);

    expect(await screen.findByText(/Aucun trade ne correspond/)).toBeInTheDocument();
    expect(screen.queryByText("Votre journal est vide")).not.toBeInTheDocument();
  });

  it("erreur serveur : message et bouton Réessayer qui relance la requête", async () => {
    let attempts = 0;
    stubApi((c) => {
      if (!c.path.startsWith("/trades/")) return undefined;
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, 500) : page([makeTrade({ name: "Revenu" })]);
    });
    const user = userEvent.setup();
    renderWithProviders(<TradesList />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Impossible de charger/);
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    expect((await screen.findAllByText("Revenu")).length).toBeGreaterThan(0);
  });

  it("affiche statut et RR en texte (pas seulement en couleur)", async () => {
    stubApi((c) =>
      c.path.startsWith("/trades/")
        ? page([makeTrade({ status: "LOSS", realized_rr: "-1.0000" })])
        : undefined,
    );
    renderWithProviders(<TradesList />);

    expect((await screen.findAllByText("Perdant")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("−1 R").length).toBeGreaterThan(0);
  });
});

describe("TradesList — filtres et navigation (état dans l'URL)", () => {
  it("transmet les filtres de l'URL à l'API", async () => {
    search = "status=WIN&market_type=CRYPTO&search=btc&ordering=asset&page=2";
    const { calls } = stubApi((c) => (c.path.startsWith("/trades/") ? page([makeTrade()], 30) : undefined));
    renderWithProviders(<TradesList />);

    await waitFor(() => expect(calls.some((c) => c.path.startsWith("/trades/"))).toBe(true));
    const url = new URLSearchParams(calls.find((c) => c.path.startsWith("/trades/"))!.path.split("?")[1]);
    expect(url.get("status")).toBe("WIN");
    expect(url.get("market_type")).toBe("CRYPTO");
    expect(url.get("search")).toBe("btc");
    expect(url.get("ordering")).toBe("asset");
    expect(url.get("page")).toBe("2");
  });

  it("la recherche est temporisée puis écrite dans l'URL en revenant à la page 1", async () => {
    search = "page=3";
    stubApi((c) => (c.path.startsWith("/trades/") ? page([makeTrade()], 100) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<TradesList />);
    await screen.findAllByText("Breakout Londres");

    await user.type(screen.getByLabelText(/Recherche/), "eur");
    expect(replace).not.toHaveBeenCalled(); // pas d'appel à chaque frappe
    await waitFor(() => expect(replace).toHaveBeenCalled(), { timeout: 2000 });

    const target = replace.mock.calls.at(-1)![0] as string;
    expect(target).toContain("search=eur");
    expect(target).not.toContain("page=");
  });

  it("pagination : Suivant ajoute page=2, Précédent est désactivé en page 1", async () => {
    stubApi((c) => (c.path.startsWith("/trades/") ? page([makeTrade()], 45) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<TradesList />);
    await screen.findAllByText("Breakout Londres");

    expect(screen.getByRole("button", { name: /Précédent/ })).toBeDisabled();
    expect(screen.getByText(/45 trades · page 1 sur 3/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Suivant/ }));
    expect(replace).toHaveBeenCalledWith("/trades?page=2", { scroll: false });
  });

  it("Réinitialiser vide l'URL et n'est actif que s'il y a des filtres", async () => {
    search = "status=OPEN";
    stubApi((c) => (c.path.startsWith("/trades/") ? page([makeTrade()]) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<TradesList />);
    await screen.findAllByText("Breakout Londres");

    await user.click(screen.getByRole("button", { name: /Réinitialiser/ }));
    expect(replace).toHaveBeenCalledWith("/trades", { scroll: false });
  });
});
