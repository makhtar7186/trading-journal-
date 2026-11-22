import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeXHR } from "@/test/fake-xhr";
import { ApiError } from "@/services/api-client";
import { makeScreenshot } from "@/test/utils";
import { uploadErrorMessage, uploadScreenshot } from "./api";

beforeEach(() => {
  FakeXHR.reset();
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  document.cookie = "tj_csrftoken=tok123";
});
afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "tj_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

const file = () => new File(["x"], "setup.png", { type: "image/png" });
const start = (extra = {}) => uploadScreenshot({ tradeId: "t1", file: file(), category: "DURING", ...extra });
const lastXhr = async () => {
  await vi.waitFor(() => expect(FakeXHR.instances.length).toBe(1));
  return FakeXHR.instances[0];
};

describe("uploadScreenshot", () => {
  it("envoie un multipart authentifié (cookies + CSRF) vers le bon trade", async () => {
    const promise = start({ description: "ma note" });
    const xhr = await lastXhr();
    expect(xhr.method).toBe("POST");
    expect(xhr.url).toBe("/api/v1/trades/t1/screenshots/");
    expect(xhr.withCredentials).toBe(true);
    expect(xhr.headers["X-CSRFToken"]).toBe("tok123");
    expect((xhr.body as FormData).get("category")).toBe("DURING");
    expect((xhr.body as FormData).get("description")).toBe("ma note");
    expect(((xhr.body as FormData).get("files") as File).name).toBe("setup.png");

    xhr.respond(201, [makeScreenshot()]);
    await expect(promise).resolves.toEqual([makeScreenshot()]);
  });

  it("n'envoie pas de description vide", async () => {
    const promise = start();
    const xhr = await lastXhr();
    expect((xhr.body as FormData).has("description")).toBe(false);
    xhr.respond(201, []);
    await promise;
  });

  it("remonte la progression réelle de l'envoi", async () => {
    const onProgress = vi.fn();
    const promise = start({ onProgress });
    const xhr = await lastXhr();
    xhr.progress(25, 100);
    xhr.progress(1, 3);
    xhr.progress(100, 100);
    xhr.respond(201, []);
    await promise;
    expect(onProgress.mock.calls.map((c) => c[0])).toEqual([25, 33, 100]);
  });

  it("rejette avec les erreurs de champs du serveur", async () => {
    const promise = start();
    const xhr = await lastXhr();
    xhr.respond(400, { files: ["setup.png : Fichier illisible ou corrompu : ce n'est pas une image valide."] });
    const error = (await promise.catch((e) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(uploadErrorMessage(error)).toBe("Fichier illisible ou corrompu : ce n'est pas une image valide.");
  });

  it("serveur injoignable → ApiError status 0", async () => {
    const promise = start();
    (await lastXhr()).fail();
    const error = (await promise.catch((e) => e)) as ApiError;
    expect(error.status).toBe(0);
  });

  it("annulation via AbortSignal", async () => {
    const controller = new AbortController();
    const promise = start({ signal: controller.signal });
    const xhr = await lastXhr();
    controller.abort();
    expect(xhr.aborted).toBe(true);
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("uploadErrorMessage", () => {
  it("utilise le détail du fichier, sinon le premier champ, sinon le message", () => {
    expect(uploadErrorMessage(new ApiError(400, "x", { files: ["a.png : Trop gros."] }))).toBe("Trop gros.");
    expect(uploadErrorMessage(new ApiError(400, "x", { category: ["Choix invalide."] }))).toBe("Choix invalide.");
    expect(uploadErrorMessage(new ApiError(503, "Stockage indisponible."))).toBe("Stockage indisponible.");
    expect(uploadErrorMessage(new Error("boom"))).toBe("Envoi impossible.");
  });
});
