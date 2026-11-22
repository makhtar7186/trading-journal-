import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, makeScreenshot, renderWithProviders, stubApi } from "@/test/utils";
import { ScreenshotGallery } from "./screenshot-gallery";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

afterEach(() => vi.unstubAllGlobals());

const SHOTS = [
  makeScreenshot({ id: "a", original_filename: "avant.png", category: "BEFORE", description: "Setup H1" }),
  makeScreenshot({ id: "b", original_filename: "pendant.png", category: "DURING" }),
  makeScreenshot({ id: "c", original_filename: "apres.png", category: "AFTER", description: "Résultat" }),
  makeScreenshot({ id: "d", original_filename: "avant2.png", category: "BEFORE" }),
];

const isList = (path: string) => path.startsWith("/trades/t1/screenshots/");

function renderGallery(shots = SHOTS) {
  const api = stubApi((c) => (isList(c.path) ? jsonResponse(shots) : undefined));
  renderWithProviders(<ScreenshotGallery tradeId="t1" />);
  return api;
}

describe("ScreenshotGallery — états", () => {
  it("chargement puis état vide explicite", async () => {
    stubApi((c) => (isList(c.path) ? jsonResponse([]) : undefined));
    renderWithProviders(<ScreenshotGallery tradeId="t1" />);
    expect(screen.getByRole("status", { name: /Chargement/ })).toBeInTheDocument();
    expect(await screen.findByText("Aucune capture")).toBeInTheDocument();
  });

  it("erreur : message et bouton Réessayer", async () => {
    let attempts = 0;
    stubApi((c) => {
      if (!isList(c.path)) return undefined;
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, 500) : jsonResponse(SHOTS);
    });
    const user = userEvent.setup();
    renderWithProviders(<ScreenshotGallery tradeId="t1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/Impossible de charger/);
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findAllByRole("button", { name: /Agrandir/ })).toHaveLength(SHOTS.length);
  });

  it("affiche les images depuis l'URL authentifiée de l'API (jamais une URL publique)", async () => {
    renderGallery();
    const img = await screen.findByAltText("Setup H1");
    expect(img).toHaveAttribute("src", "/api/v1/screenshots/s1/file/");
  });

  it("image qui ne charge pas : repli accessible au lieu d'une icône cassée", async () => {
    renderGallery([makeScreenshot({ id: "a", description: "Cassée" })]);
    fireEvent.error(await screen.findByAltText("Cassée"));
    expect(await screen.findByLabelText("Image indisponible")).toBeInTheDocument();
  });
});

describe("ScreenshotGallery — filtres par catégorie", () => {
  it("compte par catégorie et filtre la grille", async () => {
    const user = userEvent.setup();
    renderGallery();
    await screen.findByRole("tablist");

    expect(screen.getByRole("tab", { name: "Toutes (4)" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Avant (2)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Pendant (1)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Après (1)" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Après (1)" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("button", { name: /Agrandir : Résultat/ })).toBeInTheDocument();
  });
});

describe("ScreenshotGallery — visionneuse", () => {
  it("ouvre en grand, navigue au clavier et aux boutons, bornes désactivées", async () => {
    const user = userEvent.setup();
    renderGallery();
    await user.click(await screen.findByRole("button", { name: /Agrandir : Setup H1/ }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("avant.png")).toBeInTheDocument();
    expect(within(dialog).getByText("1 / 4")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Capture précédente" })).toBeDisabled();

    await user.keyboard("{ArrowRight}");
    expect(within(dialog).getByText("2 / 4")).toBeInTheDocument();
    expect(within(dialog).getByText("pendant.png")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Capture suivante" }));
    expect(within(dialog).getByText("3 / 4")).toBeInTheDocument();
    await user.keyboard("{ArrowLeft}");
    expect(within(dialog).getByText("2 / 4")).toBeInTheDocument();

    await user.keyboard("{ArrowRight}{ArrowRight}{ArrowRight}");
    expect(within(dialog).getByText("4 / 4")).toBeInTheDocument(); // ne dépasse pas la dernière
    expect(within(dialog).getByRole("button", { name: "Capture suivante" })).toBeDisabled();
  });

  it("Échap ferme la visionneuse", async () => {
    const user = userEvent.setup();
    renderGallery();
    await user.click(await screen.findByRole("button", { name: /Agrandir : Setup H1/ }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("navigue seulement parmi les captures du filtre actif", async () => {
    const user = userEvent.setup();
    renderGallery();
    await user.click(await screen.findByRole("tab", { name: "Avant (2)" }));
    await user.click(screen.getAllByRole("button", { name: /Agrandir/ })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("1 / 2")).toBeInTheDocument();
  });
});

describe("ScreenshotGallery — modification et suppression", () => {
  it("modifie la description (PATCH ne contient que catégorie et description)", async () => {
    const { calls } = stubApi((c) => {
      if (isList(c.path)) return jsonResponse(SHOTS);
      if (c.method === "PATCH") return jsonResponse(makeScreenshot({ id: "b" }));
      return undefined;
    });
    const user = userEvent.setup();
    renderWithProviders(<ScreenshotGallery tradeId="t1" />);

    await user.click(await screen.findByRole("button", { name: "Modifier pendant.png" }));
    const field = await screen.findByLabelText("Description");
    await user.type(field, "Entrée confirmée");
    await user.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.path).toBe("/screenshots/b/");
    expect(patch.body).toEqual({ category: "DURING", description: "Entrée confirmée" });
  });

  it("le formulaire d'édition repart des valeurs de la capture choisie", async () => {
    renderGallery();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Modifier avant.png" }));
    expect(await screen.findByLabelText("Description")).toHaveValue("Setup H1");
  });

  it("supprime après confirmation, jamais directement", async () => {
    const { calls } = stubApi((c) => {
      if (isList(c.path)) return jsonResponse(SHOTS);
      if (c.method === "DELETE") return jsonResponse(null, 204);
      return undefined;
    });
    const user = userEvent.setup();
    renderWithProviders(<ScreenshotGallery tradeId="t1" />);

    await user.click(await screen.findByRole("button", { name: "Supprimer apres.png" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false); // pas encore
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/irréversible/);

    await user.click(within(dialog).getByRole("button", { name: "Supprimer" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
    expect(calls.find((c) => c.method === "DELETE")!.path).toBe("/screenshots/c/");
  });

  it("Annuler ne supprime rien", async () => {
    const { calls } = renderGallery();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Supprimer apres.png" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Annuler" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });
});
