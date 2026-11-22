import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

const push = vi.hoisted(() => vi.fn());

import ErrorPage from "./error";
import GlobalError from "./global-error";
import NotFound from "./not-found";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(() => vi.restoreAllMocks());

describe("pages d'erreur", () => {
  it("erreur de page : message rassurant, aucun détail technique, bouton Réessayer", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    render(<ErrorPage error={new Error("SELECT * FROM secret – stack trace")} retry={retry} />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Une erreur est survenue");
    expect(alert).not.toHaveTextContent(/SELECT|stack|secret/);
    await userEvent.setup().click(screen.getByRole("button", { name: "Réessayer" }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("« Retour au dashboard » navigue sans rechargement complet", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorPage error={new Error("x")} retry={() => {}} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Retour au dashboard" }));
    expect(push).toHaveBeenCalledWith("/dashboard");
  });

  it("l'erreur est journalisée pour le débogage", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const error = new Error("boom");
    render(<ErrorPage error={error} retry={() => {}} />);
    expect(spy).toHaveBeenCalledWith(error);
  });

  it("erreur du layout racine : document autonome en français avec Réessayer", async () => {
    // global-error rend <html> : on le monte dans un conteneur et on inspecte la sortie.
    vi.spyOn(console, "error").mockImplementation(() => {}); // React avertit d'un <html> imbriqué dans le test
    const retry = vi.fn();
    render(<GlobalError error={new Error("x")} retry={retry} />, { container: document.documentElement });
    expect(screen.getByRole("alert")).toHaveTextContent("L'application a rencontré une erreur");
    await userEvent.setup().click(screen.getByRole("button", { name: "Réessayer" }));
    expect(retry).toHaveBeenCalled();
  });

  it("page introuvable : explication et retour au dashboard", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { name: "Page introuvable" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Retour au dashboard" })).toHaveAttribute("href", "/dashboard");
  });
});
