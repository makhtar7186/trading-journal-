"use client";

/**
 * Dernier filet : erreur dans le layout racine. Ce fichier remplace le document entier et n'hérite
 * ni des styles globaux ni du thème : styles en ligne, thème sombre appliqué ici.
 */
export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <html lang="fr">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0b0f17",
          color: "#e6e9ef",
          fontFamily: "system-ui, sans-serif",
          padding: "1rem",
        }}
      >
        <title>Erreur · Trading Journal</title>
        <div role="alert" style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: "1.25rem" }}>L&apos;application a rencontré une erreur</h1>
          <p style={{ color: "#9aa4b2", fontSize: ".9rem" }}>Vos données ne sont pas affectées. Réessayez ou rechargez la page.</p>
          <button
            onClick={() => retry()}
            style={{ marginTop: 16, padding: "10px 18px", borderRadius: 8, border: 0, background: "#4f46e5", color: "#fff", fontSize: ".95rem", cursor: "pointer" }}
          >
            Réessayer
          </button>
        </div>
      </body>
    </html>
  );
}
