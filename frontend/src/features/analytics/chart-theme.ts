/**
 * Couleurs des graphiques (miroir des tokens de globals.css : SVG et canvas n'héritent pas toujours des variables CSS).
 * Gain / perte = polarité ; l'identité ne repose jamais sur la couleur seule (signe, libellés, tableau de données).
 */
export const CHART = {
  line: "#818cf8", // série unique (courbe de performance)
  positive: "#34d399",
  negative: "#f87171",
  neutral: "#9aa4b2",
  surface: "#111827", // fond des cartes : anneau des points, séparation des segments
  grid: "rgb(255 255 255 / 8%)",
  axis: "#9aa4b2",
  onFill: "#0b0f17", // texte posé sur un aplat clair
} as const;

export const AXIS_TICK = { fill: CHART.axis, fontSize: 12 } as const;
