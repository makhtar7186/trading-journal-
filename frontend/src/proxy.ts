import { NextResponse, type NextRequest } from "next/server";

/** Indications d'origine qu'un relais (reverse proxy, tunnel…) ajoute ; le serveur Next les réécrit ensuite. */
const ORIGIN_HEADERS = ["x-forwarded-for", "forwarded", "x-real-ip"];
const INTERNAL_HEADER = "x-tj-forwarded";

/**
 * Proxy same-origin : le navigateur n'appelle que ce serveur (`/api/...`), qui relaie vers Django.
 * Cela évite CORS et simplifie cookies de session et CSRF.
 *
 * L'adresse du backend est lue à l'EXÉCUTION (variable BACKEND_INTERNAL_URL), contrairement aux `rewrites`
 * de next.config qui sont figés au build : indispensable pour la version desktop où les ports sont choisis
 * au lancement. Le chemin est conservé tel quel, slash final compris (Django l'exige).
 *
 * Sécurité : le serveur Next réécrit X-Forwarded-For, ce qui masquerait au backend un relais placé devant
 * l'application. On recopie donc ce que le client a envoyé dans un en-tête interne (que le backend traite comme
 * un indice d'origine distante). Un en-tête du même nom fourni par le client est TOUJOURS supprimé d'abord.
 */
export function proxy(request: NextRequest) {
  const backend = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";
  const { pathname, search } = request.nextUrl;

  const headers = new Headers(request.headers);
  headers.delete(INTERNAL_HEADER);
  const hint = ORIGIN_HEADERS.map((name) => request.headers.get(name)).filter(Boolean).join(", ");
  if (hint) headers.set(INTERNAL_HEADER, hint);

  return NextResponse.rewrite(new URL(`${pathname}${search}`, backend), { request: { headers } });
}

export const config = {
  matcher: "/api/:path*",
};
