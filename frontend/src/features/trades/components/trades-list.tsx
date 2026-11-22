"use client";

import { useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";

import { RValue } from "@/components/shared/r-value";
import { StatusBadge } from "@/components/shared/status-badge";
import { EmptyState, ErrorState, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTimeZone } from "@/features/auth/auth-provider";
import { formatDateTime } from "@/lib/datetime";
import { formatR } from "@/lib/format";
import { DIRECTION_LABEL, MARKET_LABEL } from "@/lib/labels";
import { useTrades } from "../hooks";
import { TradeFilters, type TradeFilterValues } from "./trade-filters";

const PAGE_SIZE = 20;
const FILTER_KEYS = ["search", "status", "market_type", "direction", "strategy", "date_from", "date_to"] as const;

/** L'état (filtres, tri, page) vit dans l'URL : lien partageable, retour arrière fiable. */
export function TradesList() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tz = useTimeZone();

  const values: TradeFilterValues = useMemo(
    () => ({
      search: searchParams.get("search") ?? "",
      status: searchParams.get("status") ?? "",
      market_type: searchParams.get("market_type") ?? "",
      direction: searchParams.get("direction") ?? "",
      strategy: searchParams.get("strategy") ?? "",
      date_from: searchParams.get("date_from") ?? "",
      date_to: searchParams.get("date_to") ?? "",
      ordering: searchParams.get("ordering") ?? "-trade_date",
    }),
    [searchParams],
  );
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const hasActiveFilters = FILTER_KEYS.some((key) => values[key] !== "");

  const navigate = useCallback(
    (patch: Record<string, string | number>) => {
      const next = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(patch)) {
        if (value === "" || value === undefined || (key === "page" && Number(value) <= 1)) next.delete(key);
        else if (key === "ordering" && value === "-trade_date") next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const onFilterChange = useCallback(
    (patch: Partial<TradeFilterValues>) => navigate({ ...patch, page: 1 }),
    [navigate],
  );

  const query = useTrades({
    page,
    page_size: PAGE_SIZE,
    ...values,
    status: values.status,
  });

  const total = query.data?.count ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const trades = query.data?.results ?? [];

  return (
    <>
      <TradeFilters
        values={values}
        onChange={onFilterChange}
        hasActiveFilters={hasActiveFilters}
        onReset={() => router.replace(pathname, { scroll: false })}
      />

      {query.isError ? (
        <ErrorState message="Impossible de charger les trades." onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <LoadingRows />
      ) : trades.length === 0 ? (
        hasActiveFilters ? (
          <EmptyState
            title="Aucun trade ne correspond à ces filtres"
            description="Modifiez ou réinitialisez les filtres pour élargir la recherche."
          />
        ) : (
          <EmptyState
            title="Votre journal est vide"
            description="Ajoutez votre premier trade pour commencer à suivre vos performances."
            action={
              <Button asChild>
                <Link href="/trades/new">
                  <Plus aria-hidden /> Ajouter un trade
                </Link>
              </Button>
            }
          />
        )
      ) : (
        <div aria-busy={query.isFetching}>
          {/* Tableau : tablette et desktop */}
          <div className="hidden overflow-hidden rounded-xl border border-border md:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Trade</TableHead>
                  <TableHead>Actif</TableHead>
                  <TableHead>Sens</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="hidden text-right xl:table-cell">RR prévu</TableHead>
                  <TableHead className="text-right">RR réalisé</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((trade) => (
                  <TableRow key={trade.id}>
                    <TableCell className="whitespace-nowrap text-muted-foreground">
                      {formatDateTime(trade.trade_date, tz)}
                    </TableCell>
                    <TableCell className="max-w-64 truncate font-medium">
                      <Link href={`/trades/${trade.id}`} className="hover:underline focus-visible:underline">
                        {trade.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-xs">{trade.asset}</span>
                      <span className="ml-2 hidden text-xs text-muted-foreground xl:inline">
                        {MARKET_LABEL[trade.market_type]}
                      </span>
                    </TableCell>
                    <TableCell>{DIRECTION_LABEL[trade.direction]}</TableCell>
                    <TableCell>
                      <StatusBadge status={trade.status} />
                    </TableCell>
                    <TableCell className="tabular hidden text-right text-muted-foreground xl:table-cell">
                      {formatR(trade.planned_rr)}
                    </TableCell>
                    <TableCell className="text-right">
                      <RValue value={trade.realized_rr} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Cartes : mobile */}
          <ul className="space-y-2 md:hidden">
            {trades.map((trade) => (
              <li key={trade.id}>
                <Link
                  href={`/trades/${trade.id}`}
                  className="block rounded-xl border border-border bg-card p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 truncate font-medium">{trade.name}</p>
                    <StatusBadge status={trade.status} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <span className="font-mono">{trade.asset}</span> · {DIRECTION_LABEL[trade.direction]} ·{" "}
                    {formatDateTime(trade.trade_date, tz)}
                  </p>
                  <p className="mt-2 text-sm">
                    <span className="text-muted-foreground">RR réalisé : </span>
                    <RValue value={trade.realized_rr} className="font-medium" />
                  </p>
                </Link>
              </li>
            ))}
          </ul>

          <nav aria-label="Pagination" className="mt-4 flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {total} trade{total > 1 ? "s" : ""} · page {page} sur {pageCount}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" disabled={page <= 1} onClick={() => navigate({ page: page - 1 })}>
                <ChevronLeft aria-hidden /> Précédent
              </Button>
              <Button variant="outline" disabled={page >= pageCount} onClick={() => navigate({ page: page + 1 })}>
                Suivant <ChevronRight aria-hidden />
              </Button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
