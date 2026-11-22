import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, renderWithProviders, stubApi, TEST_USER } from "@/test/utils";
import RegisterPage from "./page";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

beforeEach(() => replace.mockReset());
afterEach(() => vi.unstubAllGlobals());

const STRONG = "Correct-horse-battery-9";

/** Session absente + création de compte proposée (ou non). */
function stub({ enabled = true, hasUsers = false, register }: { enabled?: boolean; hasUsers?: boolean; register?: Response } = {}) {
  return stubApi((call) => {
    if (call.path === "/auth/me/") return jsonResponse({ detail: "Non authentifié." }, 403);
    if (call.path === "/auth/registration/") return jsonResponse({ enabled, has_users: hasUsers });
    if (call.path === "/auth/register/") return register;
    return undefined;
  });
}

async function fill(user: ReturnType<typeof userEvent.setup>, values: { username?: string; email?: string; password?: string; confirm?: string }) {
  if (values.username !== undefined) await user.type(screen.getByLabelText("Identifiant"), values.username);
  if (values.email !== undefined) await user.type(screen.getByLabelText(/E-mail/), values.email);
  if (values.password !== undefined) await user.type(screen.getByLabelText("Mot de passe"), values.password);
  if (values.confirm !== undefined) await user.type(screen.getByLabelText("Confirmer le mot de passe"), values.confirm);
}

describe("page de création de compte", () => {
  it("premier lancement : message de bienvenue", async () => {
    stub({ hasUsers: false });
    renderWithProviders(<RegisterPage />);
    expect(await screen.findByText(/Bienvenue/)).toBeInTheDocument();
  });

  it("création désactivée ou non locale : explication, aucun formulaire", async () => {
    stub({ enabled: false });
    renderWithProviders(<RegisterPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("La création de compte n'est pas disponible ici.");
    expect(screen.queryByLabelText("Mot de passe")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour à la connexion" })).toHaveAttribute("href", "/login");
  });

  it("valide les champs côté client sans appeler le serveur", async () => {
    const { calls } = stub();
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");

    await fill(user, { username: "ab", email: "pas-un-email", password: "court", confirm: "autre" });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));

    expect(await screen.findByText("Au moins 3 caractères.")).toBeInTheDocument();
    expect(screen.getByText("Adresse e-mail invalide.")).toBeInTheDocument();
    expect(screen.getByText("Au moins 8 caractères.")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/auth/register/")).toBe(false);
  });

  it("refuse un identifiant avec espaces ou caractères interdits", async () => {
    stub();
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");
    await fill(user, { username: "mon nom", password: STRONG, confirm: STRONG });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));
    expect(await screen.findByText(/pas d'espaces/)).toBeInTheDocument();
  });

  it("les mots de passe doivent correspondre", async () => {
    stub();
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");
    await fill(user, { username: "alice", password: STRONG, confirm: STRONG + "x" });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));
    expect(await screen.findByText("Les mots de passe ne correspondent pas.")).toBeInTheDocument();
  });

  it("crée le compte : envoie fuseau et CSRF, connecte et redirige vers le dashboard", async () => {
    const { calls } = stub({ register: jsonResponse(TEST_USER, 201) });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");

    await fill(user, { username: "  alice  ", email: "alice@example.com", password: STRONG, confirm: STRONG });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    const paths = calls.map((c) => c.path);
    expect(paths.indexOf("/auth/csrf/")).toBeLessThan(paths.indexOf("/auth/register/"));
    const body = calls.find((c) => c.path === "/auth/register/")!.body as Record<string, string>;
    expect(body.username).toBe("alice"); // espaces retirés
    expect(body.email).toBe("alice@example.com");
    expect(body.password_confirm).toBe(STRONG);
    expect(body.timezone).toMatch(/^[A-Za-z_]+(\/[A-Za-z_+-]+)*$/);
  });

  it("affiche les erreurs du serveur sur le bon champ (identifiant pris, mot de passe faible)", async () => {
    stub({
      register: jsonResponse(
        { username: ["Cet identifiant est déjà utilisé."], password: ["Ce mot de passe est trop courant.", "Ce mot de passe est entièrement numérique."] },
        400,
      ),
    });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");
    await fill(user, { username: "alice", password: STRONG, confirm: STRONG });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));

    expect(await screen.findByText("Cet identifiant est déjà utilisé.")).toBeInTheDocument();
    expect(screen.getByText(/trop courant\. Ce mot de passe est entièrement numérique\./)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("limitation (429) : message clair", async () => {
    stub({ register: jsonResponse({ detail: "Throttled" }, 429) });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");
    await fill(user, { username: "alice", password: STRONG, confirm: STRONG });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));
    expect(await screen.findByText(/Trop de tentatives/)).toBeInTheDocument();
  });

  it("refus 403 du serveur (ex. accès non local) : message, pas de redirection", async () => {
    stub({ register: jsonResponse({ detail: "La création de compte est désactivée." }, 403) });
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />);
    await screen.findByLabelText("Identifiant");
    await fill(user, { username: "alice", password: STRONG, confirm: STRONG });
    await user.click(screen.getByRole("button", { name: "Créer mon compte" }));
    expect(await screen.findByText("La création de compte est désactivée.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("les mots de passe sont masqués et le gestionnaire de mots de passe est guidé", async () => {
    stub();
    renderWithProviders(<RegisterPage />);
    const password = await screen.findByLabelText("Mot de passe");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByLabelText("Confirmer le mot de passe")).toHaveAttribute("type", "password");
  });
});
