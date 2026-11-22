import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build autonome (server.js + dépendances tracées) : utilisé par la version desktop.
  output: "standalone",
  outputFileTracingRoot: process.cwd(),
  // Dev sous Docker Desktop (Windows) : les événements de fichiers ne traversent pas le bind mount.
  // Activé uniquement si WATCHPACK_POLLING=true (défini dans docker-compose.yml, jamais en prod).
  ...(process.env.WATCHPACK_POLLING === "true" ? { watchOptions: { pollIntervalMs: 1000 } } : {}),
  // Django exige les slashs finaux (/api/v1/trades/) : on ne les retire pas.
  skipTrailingSlashRedirect: true,
  // Le proxy /api → backend est dans src/proxy.ts (adresse lue à l'exécution).
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
        ],
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
