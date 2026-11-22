import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeXHR } from "@/test/fake-xhr";
import { jsonResponse, makeScreenshot, renderWithProviders, stubApi } from "@/test/utils";
import { MAX_FILE_BYTES } from "../api";
import { ScreenshotUploader } from "./screenshot-uploader";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const png = (name = "a.png") => new File(["img"], name, { type: "image/png" });
const setup = () => userEvent.setup({ applyAccept: false });
const input = () => screen.getByLabelText("Sélectionner des captures d'écran") as HTMLInputElement;

beforeEach(() => {
  FakeXHR.reset();
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
  stubApi((c) => (c.path.startsWith("/trades/t1/screenshots") ? jsonResponse([]) : undefined));
  document.cookie = "tj_csrftoken=tok";
});
afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "tj_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("ScreenshotUploader — sélection et contrôles côté client", () => {
  it("affiche un aperçu et un bouton d'envoi pour les fichiers valides", async () => {
    const user = setup();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [png("a.png"), png("b.png")]);

    expect(screen.getByAltText("Aperçu de a.png")).toHaveAttribute("src", "blob:preview");
    expect(screen.getByRole("button", { name: /Envoyer 2 fichiers/ })).toBeEnabled();
  });

  it("refuse un format non pris en charge sans l'envoyer", async () => {
    const user = setup();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [new File(["<svg/>"], "logo.svg", { type: "image/svg+xml" })]);

    expect(screen.getByRole("alert")).toHaveTextContent(/Format non pris en charge/);
    expect(screen.getByRole("button", { name: /Envoyer 0 fichier/ })).toBeDisabled();
    expect(FakeXHR.instances).toHaveLength(0);
  });

  it("refuse un fichier trop volumineux", async () => {
    const user = setup();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    const big = png("gros.png");
    Object.defineProperty(big, "size", { value: MAX_FILE_BYTES + 1 });
    await user.upload(input(), [big]);

    expect(screen.getByRole("alert")).toHaveTextContent(/trop volumineux/);
    expect(screen.getByRole("button", { name: /Envoyer 0 fichier/ })).toBeDisabled();
  });

  it("permet de retirer un fichier de la file et libère son aperçu", async () => {
    const user = setup();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [png("a.png")]);
    await user.click(screen.getByRole("button", { name: "Retirer a.png" }));

    expect(screen.queryByText("a.png")).not.toBeInTheDocument();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });

  it("utilise la catégorie par défaut choisie pour les fichiers ajoutés ensuite", async () => {
    const user = setup();
    FakeXHR.responder = (xhr) => xhr.respond(201, [makeScreenshot()]);
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);

    await user.click(screen.getByRole("combobox", { name: /Catégorie des nouveaux fichiers/ }));
    await user.click(await screen.findByRole("option", { name: "Après" }));
    await user.upload(input(), [png("a.png")]);
    await user.click(screen.getByRole("button", { name: /Envoyer 1 fichier/ }));

    await waitFor(() => expect(FakeXHR.instances).toHaveLength(1));
    expect((FakeXHR.instances[0].body as FormData).get("category")).toBe("AFTER");
  });
});

describe("ScreenshotUploader — envoi", () => {
  it("envoie les fichiers un par un, avec progression, puis vide la file", async () => {
    const user = setup();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [png("a.png"), png("b.png")]);
    await user.click(screen.getByRole("button", { name: /Envoyer 2 fichiers/ }));

    // 1er fichier en cours : barre de progression, 2e pas encore démarré
    await waitFor(() => expect(FakeXHR.instances).toHaveLength(1));
    FakeXHR.instances[0].progress(40, 100);
    const bar = await screen.findByRole("progressbar", { name: "Envoi de a.png" });
    await waitFor(() => expect(bar).toHaveAttribute("aria-valuenow", "40"));
    expect(FakeXHR.instances).toHaveLength(1);

    FakeXHR.instances[0].respond(201, [makeScreenshot({ id: "1" })]);
    await waitFor(() => expect(FakeXHR.instances).toHaveLength(2));
    expect(((FakeXHR.instances[1].body as FormData).get("files") as File).name).toBe("b.png");
    FakeXHR.instances[1].respond(201, [makeScreenshot({ id: "2" })]);

    await waitFor(() => expect(screen.queryByRole("list", { name: "Fichiers à envoyer" })).not.toBeInTheDocument());
  });

  it("garde en file un fichier refusé par le serveur, avec son message, et permet de réessayer", async () => {
    const user = setup();
    FakeXHR.responder = (xhr) => {
      const name = ((xhr.body as FormData).get("files") as File).name;
      if (name === "mauvais.png" && FakeXHR.instances.length <= 2) {
        xhr.respond(400, { files: ["mauvais.png : Fichier illisible ou corrompu : ce n'est pas une image valide."] });
      } else {
        xhr.respond(201, [makeScreenshot()]);
      }
    };
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [png("bon.png"), png("mauvais.png")]);
    await user.click(screen.getByRole("button", { name: /Envoyer 2 fichiers/ }));

    const list = await screen.findByRole("list", { name: "Fichiers à envoyer" });
    await waitFor(() => expect(within(list).queryByText("bon.png")).not.toBeInTheDocument()); // envoyé et retiré
    expect(within(list).getByText("mauvais.png")).toBeInTheDocument();
    expect(await within(list).findByRole("alert")).toHaveTextContent("Fichier illisible ou corrompu");

    // Réessai : le serveur accepte désormais ce fichier
    FakeXHR.responder = (xhr) => xhr.respond(201, [makeScreenshot()]);
    await user.click(screen.getByRole("button", { name: /Envoyer 1 fichier/ }));
    await waitFor(() => expect(screen.queryByRole("list", { name: "Fichiers à envoyer" })).not.toBeInTheDocument());
  });

  it("affiche l'erreur réseau et conserve le fichier", async () => {
    const user = setup();
    FakeXHR.responder = (xhr) => xhr.fail();
    renderWithProviders(<ScreenshotUploader tradeId="t1" />);
    await user.upload(input(), [png("a.png")]);
    await user.click(screen.getByRole("button", { name: /Envoyer 1 fichier/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/injoignable/);
    expect(screen.getByText("a.png")).toBeInTheDocument();
  });
});
