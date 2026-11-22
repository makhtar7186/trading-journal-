import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthProvider, ME_KEY, useAuth } from "./auth-provider";
import { useLogout } from "./use-logout";
import { TEST_USER } from "@/test/utils";

const replace = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const logoutApi = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ fetchMe: vi.fn(async () => TEST_USER), logout: logoutApi }));

function Probe() {
  const { user } = useAuth();
  const logout = useLogout();
  const trades = useQuery({ queryKey: ["trades", "list"], queryFn: async () => [1], enabled: false });
  return (
    <>
      <p data-testid="user">{user ? user.username : "personne"}</p>
      <p data-testid="cache">{trades.data ? "données" : "vide"}</p>
      <button onClick={() => void logout()}>sortir</button>
    </>
  );
}

function setup() {
  const client = new QueryClient();
  client.setQueryData(["trades", "list"], [1]);
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return client;
}

describe("useLogout", () => {
  it("ramène à /login ET oublie l'utilisateur (sinon la page de connexion renvoie au tableau de bord)", async () => {
    logoutApi.mockResolvedValueOnce(undefined);
    const client = setup();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));

    await userEvent.setup().click(screen.getByText("sortir"));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.getByTestId("user")).toHaveTextContent("personne"); // l'ancien comportement (clear) laissait « alice »
    expect(client.getQueryData(ME_KEY)).toBeNull();
    expect(client.getQueryData(["trades", "list"])).toBeUndefined(); // données privées retirées du cache
  });

  it("même si l'API échoue (session expirée, serveur coupé), on est déconnecté localement", async () => {
    replace.mockClear();
    logoutApi.mockRejectedValueOnce(new Error("réseau"));
    setup();
    await waitFor(() => expect(screen.getByTestId("user")).toHaveTextContent("alice"));

    await userEvent.setup().click(screen.getByText("sortir"));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.getByTestId("user")).toHaveTextContent("personne");
  });
});
