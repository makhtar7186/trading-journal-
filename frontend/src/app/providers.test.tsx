import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ME_KEY } from "@/features/auth/auth-provider";
import { ApiError } from "@/services/api-client";
import { TEST_USER } from "@/test/utils";
import { createQueryClient } from "./providers";

const toastError = vi.hoisted(() => vi.fn());
vi.mock("sonner", () => ({ toast: { error: toastError, success: vi.fn() } }));

beforeEach(() => toastError.mockReset());
afterEach(() => vi.restoreAllMocks());

const failing = (status: number) => () => Promise.reject(new ApiError(status, `HTTP ${status}`));

async function run(client: ReturnType<typeof createQueryClient>, key: unknown[], fn: () => Promise<unknown>) {
  await client.fetchQuery({ queryKey: key, queryFn: fn, retry: false }).catch(() => undefined);
}

describe("session expirée en cours d'utilisation", () => {
  it.each([401, 403])("une requête refusée (%i) déconnecte localement et prévient l'utilisateur", async (status) => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, TEST_USER);

    await run(client, ["trades", "list"], failing(status));

    expect(client.getQueryData(ME_KEY)).toBeNull(); // le layout redirige alors vers /login
    expect(toastError).toHaveBeenCalledTimes(1);
    expect(toastError.mock.calls[0][0]).toMatch(/session a expiré/);
  });

  it("plusieurs requêtes refusées d'affilée : un seul message", async () => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, TEST_USER);
    await Promise.all([run(client, ["a"], failing(403)), run(client, ["b"], failing(403)), run(client, ["c"], failing(401))]);
    expect(toastError).toHaveBeenCalledTimes(1);
  });

  it("une mutation refusée déconnecte aussi", async () => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, TEST_USER);
    await client.getMutationCache().build(client, { mutationFn: failing(403) }).execute(undefined).catch(() => undefined);
    expect(client.getQueryData(ME_KEY)).toBeNull();
  });

  it("n'agit pas pour les autres erreurs (400, 404, 500, réseau)", async () => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, TEST_USER);
    for (const status of [400, 404, 429, 500, 0]) await run(client, ["x", status], failing(status));
    await run(client, ["y"], () => Promise.reject(new Error("boom")));

    expect(client.getQueryData(ME_KEY)).toEqual(TEST_USER);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("la requête « me » gère elle-même son 403 (pas de message : l'utilisateur n'était simplement pas connecté)", async () => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, TEST_USER);
    await run(client, [...ME_KEY], failing(403));
    expect(toastError).not.toHaveBeenCalled();
  });

  it("déjà déconnecté : pas de message en double", async () => {
    const client = createQueryClient();
    client.setQueryData(ME_KEY, null);
    await run(client, ["trades"], failing(403));
    expect(toastError).not.toHaveBeenCalled();
  });
});

describe("politique de nouvelle tentative", () => {
  it("ne réessaie pas un refus (401/403/404) mais réessaie une fois une panne", async () => {
    const client = createQueryClient();
    const retry = client.getDefaultOptions().queries!.retry as (count: number, error: unknown) => boolean;

    expect(retry(0, new ApiError(403, "x"))).toBe(false);
    expect(retry(0, new ApiError(404, "x"))).toBe(false);
    expect(retry(0, new ApiError(500, "x"))).toBe(true);
    expect(retry(1, new ApiError(500, "x"))).toBe(false); // une seule nouvelle tentative
    expect(retry(0, new ApiError(0, "réseau"))).toBe(true);
  });
});
