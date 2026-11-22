import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, renderWithProviders, stubApi, TEST_USER } from "@/test/utils";
import LoginPage from "./page";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

beforeEach(() => replace.mockReset());
afterEach(() => vi.unstubAllGlobals());

/** Session absente : /auth/me/ répond 403 tant que l'utilisateur n'est pas connecté. */
function stubLoggedOut(loginResponse?: Response) {
  return stubApi((call) => {
    if (call.path === "/auth/me/") return jsonResponse({ detail: "Non authentifié." }, 403);
    if (call.path === "/auth/login/") return loginResponse;
    return undefined;
  });
}

describe("page de connexion", () => {
  it("valide les champs avant tout appel réseau", async () => {
    const { calls } = stubLoggedOut();
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Saisissez votre identifiant.")).toBeInTheDocument();
    expect(screen.getByText("Saisissez votre mot de passe.")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/login/")).toBe(false);
  });

  it("affiche l'erreur serveur sans révéler quel champ est faux", async () => {
    stubLoggedOut(jsonResponse({ detail: "Identifiants invalides." }, 400));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText("Identifiant"), "alice");
    await user.type(screen.getByLabelText("Mot de passe"), "mauvais");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Identifiants invalides.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("connecte puis redirige vers le dashboard (CSRF demandé avant le POST)", async () => {
    const { calls } = stubLoggedOut(jsonResponse(TEST_USER));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText("Identifiant"), "alice");
    await user.type(screen.getByLabelText("Mot de passe"), "secret");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    const paths = calls.map((c) => c.path);
    expect(paths.indexOf("/auth/csrf/")).toBeLessThan(paths.indexOf("/auth/login/"));
    expect(calls.find((c) => c.path === "/auth/login/")?.body).toEqual({ username: "alice", password: "secret" });
  });

  it("affiche « Créer un compte » seulement quand le serveur le propose", async () => {
    stubApi((call) => {
      if (call.path === "/auth/me/") return jsonResponse({ detail: "Non authentifié." }, 403);
      if (call.path === "/auth/registration/") return jsonResponse({ enabled: true, has_users: true });
      return undefined;
    });
    renderWithProviders(<LoginPage />);
    expect(await screen.findByRole("link", { name: "Créer un compte" })).toHaveAttribute("href", "/register");
  });

  it("premier lancement : invite explicitement à créer le premier compte", async () => {
    stubApi((call) => {
      if (call.path === "/auth/me/") return jsonResponse({ detail: "Non authentifié." }, 403);
      if (call.path === "/auth/registration/") return jsonResponse({ enabled: true, has_users: false });
      return undefined;
    });
    renderWithProviders(<LoginPage />);
    expect(await screen.findByText(/Aucun compte n'existe encore/)).toBeInTheDocument();
  });

  it("aucun lien de création quand elle est désactivée ou indisponible", async () => {
    stubLoggedOut(); // /auth/registration/ → enabled: false par défaut
    const { unmount } = renderWithProviders(<LoginPage />);
    await screen.findByRole("button", { name: "Se connecter" });
    await waitFor(() => expect(screen.queryByRole("link", { name: "Créer un compte" })).not.toBeInTheDocument());
    unmount();

    stubApi((call) => {
      if (call.path === "/auth/me/") return jsonResponse({ detail: "Non authentifié." }, 403);
      if (call.path === "/auth/registration/") return jsonResponse({}, 500);
      return undefined;
    });
    renderWithProviders(<LoginPage />);
    await screen.findByRole("button", { name: "Se connecter" });
    expect(screen.queryByRole("link", { name: "Créer un compte" })).not.toBeInTheDocument();
  });

  it("le champ mot de passe est masqué", () => {
    stubLoggedOut();
    renderWithProviders(<LoginPage />);
    expect(screen.getByLabelText("Mot de passe")).toHaveAttribute("type", "password");
  });
});
