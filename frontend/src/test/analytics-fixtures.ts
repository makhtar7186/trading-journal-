import type { CalendarMonth, EquityCurve, Group, Overview, Performance, Period } from "@/types/api";
import { jsonResponse, stubApi, type RecordedCall } from "./utils";

/** Jeu de données « A » du backend (8 trades clôturés, total 4,5 R) tel que l'API le renvoie. */
export const OVERVIEW_A: Overview = {
  closed_trades: 8,
  wins: 4,
  losses: 3,
  break_even: 1,
  open_trades: 1,
  win_rate: "57.14",
  average_realized_rr: "0.5625",
  expectancy_r: "0.5625",
  profit_factor: "2.5000",
  total_r: "4.5000",
};

export const OVERVIEW_EMPTY: Overview = {
  closed_trades: 0,
  wins: 0,
  losses: 0,
  break_even: 0,
  open_trades: 2,
  win_rate: null,
  average_realized_rr: null,
  expectancy_r: null,
  profit_factor: null,
  total_r: null,
};

export const PERFORMANCE_A: Performance = {
  gross_profit_r: "7.5000",
  gross_loss_r: "-3.0000",
  average_win_r: "1.8750",
  average_loss_r: "-1.0000",
  best_trade: { trade_id: "b", name: "XAUUSD setup 2", asset: "XAUUSD", closed_at: "2026-08-23T12:00:00Z", realized_rr: "3.0000" },
  worst_trade: { trade_id: "w", name: "EURUSD setup 5", asset: "EURUSD", closed_at: "2026-09-28T12:00:00Z", realized_rr: "-1.0000" },
  streaks: { max_win: 3, max_loss: 2, current_type: "LOSS", current_length: 1 },
};

export const EQUITY_A: EquityCurve = {
  trades: 3,
  total_r: "4.0000",
  points: [
    { index: 1, trade_id: "t1", name: "Premier", asset: "EURUSD", closed_at: "2026-11-01T10:00:00Z", realized_rr: "2.0000", cumulative_r: "2.0000" },
    { index: 2, trade_id: "t2", name: "Deuxième", asset: "XAUUSD", closed_at: "2026-11-02T10:00:00Z", realized_rr: "3.0000", cumulative_r: "5.0000" },
    { index: 3, trade_id: "t3", name: "Troisième", asset: "EURUSD", closed_at: "2026-11-03T10:00:00Z", realized_rr: "-1.0000", cumulative_r: "4.0000" },
  ],
};

const summary = {
  trades: 2,
  wins: 1,
  losses: 1,
  break_even: 0,
  win_rate: "50.00",
  total_r: "2.0000",
  expectancy_r: "1.0000",
  profit_factor: "3.0000",
};

export const GROUPS_A: Group[] = [
  { key: "XAUUSD", label: "XAUUSD", ...summary },
  { key: "BTCUSD", label: "BTCUSD", ...summary, trades: 1, wins: 1, losses: 0, win_rate: "100.00", total_r: "1.5000", expectancy_r: "1.5000", profit_factor: null },
];

export const PERIODS_A: Period[] = [
  { period: "2026-10", start: "2026-10-01", ...summary, total_r: "-1.0000" },
  { period: "2026-11", start: "2026-11-01", ...summary, total_r: "3.0000" },
];

const calendarTrade = (id: string, name: string, status: "WIN" | "LOSS" | "OPEN", rr: string | null, at: string) => ({
  id,
  name,
  asset: "EURUSD",
  market_type: "FOREX" as const,
  direction: "BUY" as const,
  status,
  realized_rr: rr,
  at,
});

/** Novembre 2026 : un jour gagnant (2 trades), un jour avec seulement un trade ouvert, un jour perdant. */
export const CALENDAR_A: CalendarMonth = {
  month: "2026-11",
  summary: { closed_trades: 3, wins: 1, losses: 2, break_even: 0, open_trades: 1, days_with_trades: 3, total_r: "0.5000" },
  days: [
    {
      date: "2026-11-10",
      closed_trades: 2,
      wins: 1,
      losses: 1,
      break_even: 0,
      open_trades: 0,
      total_r: "2.0000",
      trades: [
        calendarTrade("c1", "Breakout matin", "WIN", "3.0000", "2026-11-10T09:30:00Z"),
        calendarTrade("c2", "Retournement", "LOSS", "-1.0000", "2026-11-10T14:00:00Z"),
      ],
    },
    {
      date: "2026-11-12",
      closed_trades: 0,
      wins: 0,
      losses: 0,
      break_even: 0,
      open_trades: 1,
      total_r: null,
      trades: [calendarTrade("c3", "Trade en cours", "OPEN", null, "2026-11-12T08:00:00Z")],
    },
    {
      date: "2026-11-20",
      closed_trades: 1,
      wins: 0,
      losses: 1,
      break_even: 0,
      open_trades: 0,
      total_r: "-1.5000",
      trades: [calendarTrade("c4", "Faux départ", "LOSS", "-1.5000", "2026-11-20T10:00:00Z")],
    },
  ],
};

export const CALENDAR_EMPTY: CalendarMonth = {
  month: "2026-11",
  summary: { closed_trades: 0, wins: 0, losses: 0, break_even: 0, open_trades: 0, days_with_trades: 0, total_r: null },
  days: [],
};

type Handler = (call: RecordedCall) => Response | undefined;

/** Simule tous les endpoints analytics + la liste des trades ; `override` prend la priorité. */
export function stubAnalyticsApi(
  data: { overview?: Overview; performance?: Performance; equity?: EquityCurve; calendar?: CalendarMonth } = {},
  override?: Handler,
) {
  return stubApi((call) => {
    const custom = override?.(call);
    if (custom) return custom;
    if (call.path.startsWith("/analytics/overview/")) return jsonResponse(data.overview ?? OVERVIEW_A);
    if (call.path.startsWith("/analytics/performance/")) return jsonResponse(data.performance ?? PERFORMANCE_A);
    if (call.path.startsWith("/analytics/equity-curve/")) return jsonResponse(data.equity ?? EQUITY_A);
    if (call.path.startsWith("/analytics/calendar/")) {
      const month = queryOf(call.path).get("month");
      return jsonResponse({ ...(data.calendar ?? CALENDAR_A), ...(month ? { month } : {}) });
    }
    if (call.path.startsWith("/analytics/by-period/")) return jsonResponse({ granularity: "month", periods: PERIODS_A });
    if (call.path.startsWith("/analytics/by-")) return jsonResponse({ groups: GROUPS_A });
    if (call.path.startsWith("/trades/")) return jsonResponse({ count: 0, next: null, previous: null, results: [] });
    return undefined;
  });
}

export const queryOf = (path: string) => new URLSearchParams(path.split("?")[1] ?? "");
