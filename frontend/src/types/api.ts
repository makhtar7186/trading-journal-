export type MarketType = "FOREX" | "METALS" | "INDICES" | "CRYPTO";
export type Direction = "BUY" | "SELL";
export type TradeStatus = "OPEN" | "WIN" | "LOSS" | "BE";

/** Les décimaux transitent en chaîne (jamais de float côté JSON). */
export type DecimalString = string;

export interface User {
  id: string;
  username: string;
  email: string;
  timezone: string;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  entry_rules: string;
  exit_rules: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Trade {
  id: string;
  name: string;
  trade_date: string;
  market_type: MarketType;
  asset: string;
  direction: Direction;
  status: TradeStatus;
  planned_rr: DecimalString | null;
  realized_rr: DecimalString | null;
  strategy: string | null;
  entry_price: DecimalString | null;
  stop_loss: DecimalString | null;
  take_profit: DecimalString | null;
  notes: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export type ScreenshotCategory = "BEFORE" | "DURING" | "AFTER";

export interface Screenshot {
  id: string;
  trade: string;
  original_filename: string;
  category: ScreenshotCategory;
  description: string;
  uploaded_at: string;
  /** URL authentifiée de l'image (jamais publique). */
  file_url: string;
}

/** Analytics : tout est calculé par le backend. `null` = non défini (jamais 0 ni infini). */
export interface Overview {
  closed_trades: number;
  wins: number;
  losses: number;
  break_even: number;
  open_trades: number;
  win_rate: DecimalString | null;
  average_realized_rr: DecimalString | null;
  expectancy_r: DecimalString | null;
  profit_factor: DecimalString | null;
  total_r: DecimalString | null;
}

export interface TradeRef {
  trade_id: string;
  name: string;
  asset: string;
  closed_at: string;
  realized_rr: DecimalString;
}

export interface Performance {
  gross_profit_r: DecimalString | null;
  gross_loss_r: DecimalString | null;
  average_win_r: DecimalString | null;
  average_loss_r: DecimalString | null;
  best_trade: TradeRef | null;
  worst_trade: TradeRef | null;
  streaks: {
    max_win: number;
    max_loss: number;
    current_type: "WIN" | "LOSS" | null;
    current_length: number;
  };
}

export interface EquityPoint {
  index: number;
  trade_id: string;
  name: string;
  asset: string;
  closed_at: string;
  realized_rr: DecimalString;
  cumulative_r: DecimalString;
}

export interface EquityCurve {
  trades: number;
  total_r: DecimalString | null;
  points: EquityPoint[];
}

export interface GroupSummary {
  trades: number;
  wins: number;
  losses: number;
  break_even: number;
  win_rate: DecimalString | null;
  total_r: DecimalString | null;
  expectancy_r: DecimalString | null;
  profit_factor: DecimalString | null;
}

export interface Group extends GroupSummary {
  key: string | null;
  label: string;
}

export type Granularity = "day" | "week" | "month";

export interface Period extends GroupSummary {
  period: string;
  start: string;
}

export interface CalendarTrade {
  id: string;
  name: string;
  asset: string;
  market_type: MarketType;
  direction: Direction;
  status: TradeStatus;
  /** null tant que le trade est ouvert. */
  realized_rr: DecimalString | null;
  /** Date de clôture (clôturé) ou de prise (ouvert). */
  at: string;
}

export interface CalendarDay {
  /** YYYY-MM-DD dans le fuseau de l'utilisateur. */
  date: string;
  closed_trades: number;
  wins: number;
  losses: number;
  break_even: number;
  open_trades: number;
  /** Σ RR des trades clôturés ce jour ; null s'il n'y en a aucun (≠ 0 R). */
  total_r: DecimalString | null;
  trades: CalendarTrade[];
}

export interface CalendarMonth {
  month: string;
  summary: {
    closed_trades: number;
    wins: number;
    losses: number;
    break_even: number;
    open_trades: number;
    days_with_trades: number;
    total_r: DecimalString | null;
  };
  days: CalendarDay[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
