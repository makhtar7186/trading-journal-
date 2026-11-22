import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, makeTrade, renderWithProviders, stubApi } from "@/test/utils";
import { TradeForm } from "./trade-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => push.mockReset());
afterEach(() => vi.unstubAllGlobals());

describe("TradeForm", () => {
  it("bloque l'envoi et signale les champs obligatoires", async () => {
    const { calls } = stubApi();
    const user = userEvent.setup();
    renderWithProviders(<TradeForm />);

    await user.click(screen.getByRole("button", { name: "Enregistrer le trade" }));

    expect(await screen.findByText("Le nom est obligatoire.")).toBeInTheDocument();
    expect(screen.getByText("L'actif est obligatoire.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("refuse un RR prévu négatif côté client", async () => {
    stubApi();
    const user = userEvent.setup();
    renderWithProviders(<TradeForm />);

    await user.type(screen.getByLabelText("RR prévu"), "-1");
    await user.click(screen.getByRole("button", { name: "Enregistrer le trade" }));

    expect(await screen.findByText(/strictement positif/)).toBeInTheDocument();
  });

  it("crée un trade ouvert : actif normalisé, aucun statut envoyé, redirection vers la fiche", async () => {
    const { calls } = stubApi((c) =>
      c.method === "POST" && c.path === "/trades/" ? jsonResponse(makeTrade({ id: "new-id" }), 201) : undefined,
    );
    const user = userEvent.setup();
    renderWithProviders(<TradeForm />);

    await user.type(screen.getByLabelText("Nom du trade"), "Breakout");
    await user.type(screen.getByLabelText("Actif"), "xauusd");
    await user.type(screen.getByLabelText("RR prévu"), "2,5");
    await user.click(screen.getByRole("button", { name: "Enregistrer le trade" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/trades/new-id"));
    const body = calls.find((c) => c.method === "POST" && c.path === "/trades/")!.body as Record<string, unknown>;
    expect(body.asset).toBe("XAUUSD");
    expect(body.planned_rr).toBe("2.5");
    expect(body.realized_rr).toBeNull();
    expect(body.strategy).toBeNull();
    expect(body).not.toHaveProperty("status");
    expect(body).not.toHaveProperty("user");
  });

  it("affiche sur le champ concerné l'erreur de validation renvoyée par le serveur", async () => {
    stubApi((c) =>
      c.method === "POST" ? jsonResponse({ asset: ["Actif non pris en charge."] }, 400) : undefined,
    );
    const user = userEvent.setup();
    renderWithProviders(<TradeForm />);

    await user.type(screen.getByLabelText("Nom du trade"), "Test");
    await user.type(screen.getByLabelText("Actif"), "zzz");
    await user.click(screen.getByRole("button", { name: "Enregistrer le trade" }));

    expect(await screen.findByText("Actif non pris en charge.")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("édition : préremplit les champs et PATCH vers le bon trade", async () => {
    const trade = makeTrade({ id: "t9", name: "Ancien nom", asset: "BTCUSD", status: "WIN", realized_rr: "3.0000" });
    const { calls } = stubApi((c) => (c.method === "PATCH" ? jsonResponse(trade) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<TradeForm trade={trade} />);

    expect(screen.getByLabelText("Nom du trade")).toHaveValue("Ancien nom");
    expect(screen.getByLabelText("RR réalisé")).toHaveValue("3.0000");

    await user.clear(screen.getByLabelText("Nom du trade"));
    await user.type(screen.getByLabelText("Nom du trade"), "Nouveau nom");
    await user.click(screen.getByRole("button", { name: "Enregistrer les modifications" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/trades/t9"));
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.path).toBe("/trades/t9/");
    expect((patch.body as Record<string, unknown>).name).toBe("Nouveau nom");
    expect((patch.body as Record<string, unknown>).realized_rr).toBe("3.0000");
  });

  it("vider le RR réalisé d'un trade clôturé envoie null (réouverture)", async () => {
    const trade = makeTrade({ id: "t9", status: "WIN", realized_rr: "3.0000" });
    const { calls } = stubApi((c) => (c.method === "PATCH" ? jsonResponse(makeTrade({ id: "t9" })) : undefined));
    const user = userEvent.setup();
    renderWithProviders(<TradeForm trade={trade} />);

    await user.clear(screen.getByLabelText("RR réalisé"));
    await user.click(screen.getByRole("button", { name: "Enregistrer les modifications" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect((calls.find((c) => c.method === "PATCH")!.body as Record<string, unknown>).realized_rr).toBeNull();
  });
});
