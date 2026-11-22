import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, makeTrade, renderWithProviders, stubApi } from "@/test/utils";
import { CloseTradeDialog } from "./close-trade-dialog";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

afterEach(() => vi.unstubAllGlobals());

describe("CloseTradeDialog", () => {
  it("refuse une saisie non numérique sans appeler l'API", async () => {
    const { calls } = stubApi();
    const user = userEvent.setup();
    renderWithProviders(<CloseTradeDialog trade={makeTrade()} open onOpenChange={() => {}} />);

    await user.type(screen.getByLabelText("RR réalisé"), "abc");
    await user.click(screen.getByRole("button", { name: "Clôturer" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Saisissez un nombre/);
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("envoie uniquement realized_rr (jamais de statut) avec le point décimal", async () => {
    const { calls } = stubApi((call) =>
      call.method === "PATCH" ? jsonResponse(makeTrade({ status: "WIN", realized_rr: "2.5000" })) : undefined,
    );
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<CloseTradeDialog trade={makeTrade({ id: "abc" })} open onOpenChange={onOpenChange} />);

    await user.type(screen.getByLabelText("RR réalisé"), "2,5");
    await user.click(screen.getByRole("button", { name: "Clôturer" }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/trades/abc/");
    expect(patch?.body).toEqual({ realized_rr: "2.5" });
  });

  it("affiche l'erreur renvoyée par le serveur", async () => {
    stubApi((call) =>
      call.method === "PATCH" ? jsonResponse({ realized_rr: ["Valeur trop grande."] }, 400) : undefined,
    );
    const user = userEvent.setup();
    renderWithProviders(<CloseTradeDialog trade={makeTrade()} open onOpenChange={() => {}} />);

    await user.type(screen.getByLabelText("RR réalisé"), "99999999");
    await user.click(screen.getByRole("button", { name: "Clôturer" }));

    expect(await screen.findByText("Valeur trop grande.")).toBeInTheDocument();
  });
});
