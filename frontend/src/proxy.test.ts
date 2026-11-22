// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { config, proxy } from "./proxy";

afterEach(() => vi.unstubAllEnvs());

const target = (url: string) => proxy(new NextRequest(url)).headers.get("x-middleware-rewrite");

describe("proxy /api → backend", () => {
  it("relaie vers l'adresse lue À L'EXÉCUTION", () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://127.0.0.1:43210");
    expect(target("http://localhost:3000/api/v1/trades/")).toBe("http://127.0.0.1:43210/api/v1/trades/");
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://backend:8000");
    expect(target("http://localhost:3000/api/v1/trades/")).toBe("http://backend:8000/api/v1/trades/");
  });

  it("conserve le slash final (Django l'exige) et la chaîne de requête", () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://127.0.0.1:8000");
    expect(target("http://localhost:3000/api/v1/auth/me/")).toBe("http://127.0.0.1:8000/api/v1/auth/me/");
    expect(target("http://localhost:3000/api/v1/trades/?status=WIN&search=a%20b")).toBe(
      "http://127.0.0.1:8000/api/v1/trades/?status=WIN&search=a%20b",
    );
  });

  it("adresse par défaut si la variable est absente", () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "");
    delete process.env.BACKEND_INTERNAL_URL;
    expect(target("http://localhost:3000/api/v1/health/")).toBe("http://127.0.0.1:8000/api/v1/health/");
  });

  it("ne cible que /api (jamais les pages ni les fichiers statiques)", () => {
    expect(config.matcher).toBe("/api/:path*");
  });

  it("l'hôte du backend ne dépend jamais de l'URL demandée (pas de redirection ouverte)", () => {
    vi.stubEnv("BACKEND_INTERNAL_URL", "http://127.0.0.1:8000");
    expect(target("http://localhost:3000/api//evil.example.com/x")).toMatch(/^http:\/\/127\.0\.0\.1:8000\//);
    expect(target("http://localhost:3000/api/../../etc/passwd")).toMatch(/^http:\/\/127\.0\.0\.1:8000\//);
  });

  const forwarded = (init: Record<string, string>) => {
    const response = proxy(new NextRequest("http://localhost:3000/api/v1/auth/registration/", { headers: init }));
    const kept = (response.headers.get("x-middleware-override-headers") ?? "").split(",");
    return { value: response.headers.get("x-middleware-request-x-tj-forwarded"), kept };
  };

  it("recopie les indications de relais envoyées par le client dans un en-tête interne", () => {
    expect(forwarded({ "x-forwarded-for": "203.0.113.9" }).value).toBe("203.0.113.9");
    expect(forwarded({ "x-real-ip": "198.51.100.4" }).value).toBe("198.51.100.4");
    expect(forwarded({ forwarded: "for=203.0.113.9;proto=https" }).value).toBe("for=203.0.113.9;proto=https");
    expect(forwarded({ "x-forwarded-for": "127.0.0.1", "x-real-ip": "203.0.113.9" }).value).toBe("127.0.0.1, 203.0.113.9");
  });

  it("sans relais, aucun en-tête interne n'est transmis", () => {
    const { value, kept } = forwarded({});
    expect(value).toBeNull();
    expect(kept).not.toContain("x-tj-forwarded");
  });

  it("un en-tête interne fourni par le CLIENT est supprimé, jamais cru (pas de falsification pour paraître local)", () => {
    const { value, kept } = forwarded({ "x-tj-forwarded": "127.0.0.1" });
    expect(value).toBeNull();
    expect(kept).not.toContain("x-tj-forwarded");
    // et s'il y a vraiment un relais, c'est SA valeur qui compte, pas celle du client
    expect(forwarded({ "x-tj-forwarded": "127.0.0.1", "x-forwarded-for": "203.0.113.9" }).value).toBe("203.0.113.9");
  });

  it("les autres en-têtes (cookies, CSRF) continuent d'être transmis au backend", () => {
    const { kept } = forwarded({ cookie: "tj_sessionid=abc", "x-csrftoken": "t" });
    expect(kept).toEqual(expect.arrayContaining(["cookie", "x-csrftoken"]));
  });
});
