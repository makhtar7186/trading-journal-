import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/layout/app-shell";
import { CalendarView } from "@/features/calendar/components/calendar-view";
import { AnalyticsView } from "@/features/analytics/components/analytics-view";
import { ScreenshotGallery } from "@/features/screenshots/components/screenshot-gallery";
import { ScreenshotUploader } from "@/features/screenshots/components/screenshot-uploader";
import { SettingsView } from "@/features/settings/settings-view";
import { StrategiesView } from "@/features/strategies/components/strategies-view";
import { DashboardView } from "@/features/trades/components/dashboard-view";
import { TradeDetail } from "@/features/trades/components/trade-detail";
import { TradeForm } from "@/features/trades/components/trade-form";
import { TradesList } from "@/features/trades/components/trades-list";
import LoginPage from "@/app/(auth)/login/page";
import ErrorPage from "@/app/error";
import NotFound from "@/app/not-found";
import { stubAnalyticsApi } from "./analytics-fixtures";
import { a11yViolations } from "./a11y";
import { jsonResponse, makeScreenshot, makeTrade, renderWithProviders } from "./utils";

let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => {
  search = "";
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-15T10:00:00Z"));
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const TRADE = makeTrade({ id: "t1", status: "WIN", realized_rr: "2.0000", strategy: "s1" });
const SHOTS = [makeScreenshot({ id: "a", description: "Setup" }), makeScreenshot({ id: "b", category: "AFTER", original_filename: "b.png" })];

function stubAll() {
  return stubAnalyticsApi({}, (call) => {
    if (call.path.startsWith("/trades/t1/screenshots/")) return jsonResponse(SHOTS);
    if (call.path === "/trades/t1/") return jsonResponse(TRADE);
    if (call.path.startsWith("/trades/")) return jsonResponse({ count: 1, next: null, previous: null, results: [TRADE, makeTrade({ id: "t2", name: "Ouvert" })] });
    if (call.path.startsWith("/strategies/"))
      return jsonResponse({
        count: 1, next: null, previous: null,
        results: [{ id: "s1", name: "Breakout", description: "Cassure", entry_rules: "", exit_rules: "", is_active: true, created_at: "", updated_at: "" }],
      });
    return undefined;
  });
}

async function audit(ui: React.ReactElement, ready: () => Promise<unknown>) {
  const { container } = renderWithProviders(ui);
  await ready();
  return a11yViolations(container);
}

describe("accessibilité automatisée (axe-core, WCAG 2.x A/AA)", () => {
  it("connexion", async () => {
    stubAll();
    expect(await audit(<LoginPage />, () => screen.findByRole("button", { name: "Se connecter" }))).toEqual([]);
  });

  it("dashboard", async () => {
    stubAll();
    expect(await audit(<DashboardView />, () => screen.findByText("57,14 %"))).toEqual([]);
  });

  it("analytics", async () => {
    stubAll();
    expect(await audit(<AnalyticsView />, () => screen.findByRole("table", { name: "Résultats par stratégie" }))).toEqual([]);
  });

  it("calendrier avec un jour sélectionné", async () => {
    search = "month=2026-11&day=2026-11-10";
    stubAll();
    expect(await audit(<CalendarView />, () => screen.findByText("Résultat du jour"))).toEqual([]);
  });

  it("journal des trades", async () => {
    stubAll();
    expect(await audit(<TradesList />, () => screen.findAllByText("Breakout Londres"))).toEqual([]);
  });

  it("formulaire de trade (création)", async () => {
    stubAll();
    expect(await audit(<TradeForm />, () => screen.findByLabelText("Nom du trade"))).toEqual([]);
  });

  it("formulaire de trade (édition d'un trade clôturé)", async () => {
    stubAll();
    expect(await audit(<TradeForm trade={TRADE} />, () => screen.findByLabelText("Nom du trade"))).toEqual([]);
  });

  it("fiche d'un trade avec captures", async () => {
    stubAll();
    expect(await audit(<TradeDetail id="t1" />, () => screen.findByRole("tab", { name: /Toutes/ }))).toEqual([]);
  });

  it("galerie de captures et envoi", async () => {
    stubAll();
    const view = await audit(
      <>
        <ScreenshotUploader tradeId="t1" />
        <ScreenshotGallery tradeId="t1" />
      </>,
      () => screen.findByRole("tab", { name: /Toutes/ }),
    );
    expect(view).toEqual([]);
  });

  it("stratégies", async () => {
    stubAll();
    expect(await audit(<StrategiesView />, () => screen.findByText("Breakout"))).toEqual([]);
  });

  it("paramètres", async () => {
    stubAll();
    expect(await audit(<SettingsView />, () => screen.findByText("Fuseau horaire"))).toEqual([]);
  });

  it("structure de l'application (navigation, repères, lien d'évitement)", async () => {
    stubAll();
    const violations = await audit(<AppShell><h1>Page</h1></AppShell>, () => screen.findByRole("navigation", { name: "Navigation principale" }));
    expect(violations).toEqual([]);
    expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", "#contenu");
    expect(document.getElementById("contenu")).toBeInTheDocument();
  });

  it("pages d'erreur et 404", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { container, unmount } = renderWithProviders(<ErrorPage error={new Error("x")} retry={() => {}} />);
    expect(await a11yViolations(container)).toEqual([]);
    unmount();
    const notFound = renderWithProviders(<NotFound />);
    expect(await a11yViolations(notFound.container)).toEqual([]);
  });
});
