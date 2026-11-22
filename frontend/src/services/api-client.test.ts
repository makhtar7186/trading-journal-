import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonResponse } from "@/test/utils";
import { ApiError, apiFetch, buildQuery } from "./api-client";

const fetchMock = vi.fn();

/** Attend un échec et retourne l'ApiError (échoue le test si la requête réussit). */
const failure = (promise: Promise<unknown>) =>
  promise.then(
    () => {
      throw new Error("La requête devait échouer.");
    },
    (error: unknown) => error as ApiError,
  );

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  document.cookie = "tj_csrftoken=abc123";
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  document.cookie = "tj_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return { url, init, headers: init.headers as Record<string, string> };
}

describe("apiFetch", () => {
  it("GET : pas d'en-tête CSRF, cookies inclus, pas de cache", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await apiFetch("/trades/");
    const { url, init, headers } = lastCall();
    expect(url).toBe("/api/v1/trades/");
    expect(init.credentials).toBe("include");
    expect(init.cache).toBe("no-store");
    expect(headers["X-CSRFToken"]).toBeUndefined();
  });

  it("POST : envoie le jeton CSRF et le corps JSON", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "1" }, 201));
    await apiFetch("/trades/", { method: "POST", body: { name: "x" } });
    const { init, headers } = lastCall();
    expect(headers["X-CSRFToken"]).toBe("abc123");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ name: "x" }));
  });

  it("récupère le cookie CSRF s'il manque avant une écriture", async () => {
    document.cookie = "tj_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith("/auth/csrf/")) {
        document.cookie = "tj_csrftoken=fresh";
        return jsonResponse(null, 204);
      }
      return jsonResponse({ id: "1" });
    });
    await apiFetch("/trades/", { method: "POST", body: {} });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/csrf/");
    expect(lastCall().headers["X-CSRFToken"]).toBe("fresh");
  });

  it("204 → undefined", async () => {
    fetchMock.mockResolvedValue(jsonResponse(null, 204));
    await expect(apiFetch("/trades/1/", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("transforme les erreurs de champs DRF", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ planned_rr: ["Trop bas."], name: ["Requis."] }, 400));
    const error = await failure(apiFetch("/trades/", { method: "POST", body: {} }));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.fieldErrors).toEqual({ planned_rr: ["Trop bas."], name: ["Requis."] });
    expect(error.message).toBe("Certains champs sont invalides.");
  });

  it("reprend le message `detail`", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Identifiants invalides." }, 400));
    const error = await failure(apiFetch("/auth/login/", { method: "POST", body: {} }));
    expect(error.message).toBe("Identifiants invalides.");
  });

  it("identifie les erreurs d'authentification", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: "Informations d'authentification non fournies." }, 403));
    const error = await failure(apiFetch("/auth/me/"));
    expect(error.isAuthError).toBe(true);
  });

  it("message dédié pour le throttling (429) et les erreurs serveur", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: "Throttled" }, 429));
    expect((await failure(apiFetch("/auth/login/"))).message).toMatch(/Trop de tentatives/);
    fetchMock.mockResolvedValueOnce(new Response("<html>boom</html>", { status: 500 }));
    expect((await failure(apiFetch("/trades/"))).message).toMatch(/Erreur serveur/);
  });

  it("serveur injoignable → ApiError status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await failure(apiFetch("/trades/"));
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.isAuthError).toBe(false);
  });
});

describe("buildQuery", () => {
  it("ignore les valeurs vides et encode les autres", () => {
    expect(buildQuery({ status: "WIN", search: "", page: 2, x: undefined, y: null })).toBe("?status=WIN&page=2");
    expect(buildQuery({ search: "a b&c" })).toBe("?search=a+b%26c");
    expect(buildQuery()).toBe("");
  });
});
