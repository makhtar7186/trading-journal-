import axe from "axe-core";

/**
 * Audit d'accessibilité automatisé (axe-core, règles WCAG 2.x A/AA + bonnes pratiques).
 * - `color-contrast` est désactivé : jsdom ne calcule pas les styles réels (les contrastes des couleurs
 *   sont vérifiés à la conception, voir globals.css).
 * - `region` est désactivé : chaque vue est testée isolément, hors du layout qui fournit les repères.
 */
export async function a11yViolations(container: Element): Promise<string[]> {
  const results = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
    resultTypes: ["violations"],
  });
  return results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help} → ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`,
  );
}
