import type { Direction, MarketType, ScreenshotCategory, TradeStatus } from "@/types/api";

export const STATUS_LABEL: Record<TradeStatus, string> = {
  OPEN: "Ouvert",
  WIN: "Gagnant",
  LOSS: "Perdant",
  BE: "Break-even",
};

export const MARKET_LABEL: Record<MarketType, string> = {
  FOREX: "Forex",
  METALS: "Métaux",
  INDICES: "Indices",
  CRYPTO: "Crypto",
};

export const DIRECTION_LABEL: Record<Direction, string> = {
  BUY: "Achat",
  SELL: "Vente",
};

export const CATEGORY_LABEL: Record<ScreenshotCategory, string> = {
  BEFORE: "Avant",
  DURING: "Pendant",
  AFTER: "Après",
};

export const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABEL) as [ScreenshotCategory, string][];

export const STATUS_OPTIONS = Object.entries(STATUS_LABEL) as [TradeStatus, string][];
export const MARKET_OPTIONS = Object.entries(MARKET_LABEL) as [MarketType, string][];
export const DIRECTION_OPTIONS = Object.entries(DIRECTION_LABEL) as [Direction, string][];
