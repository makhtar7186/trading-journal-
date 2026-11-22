"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Pencil, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { RValue } from "@/components/shared/r-value";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorState, LoadingRows } from "@/components/shared/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTimeZone } from "@/features/auth/auth-provider";
import { ScreenshotsSection } from "@/features/screenshots/components/screenshots-section";
import { useStrategies } from "@/features/strategies/hooks";
import { formatDateTime } from "@/lib/datetime";
import { formatPrice, formatR } from "@/lib/format";
import { DIRECTION_LABEL, MARKET_LABEL } from "@/lib/labels";
import { ApiError } from "@/services/api-client";
import { useDeleteTrade, useTrade, useUpdateTrade } from "../hooks";
import { CloseTradeDialog } from "./close-trade-dialog";

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{children}</dd>
    </div>
  );
}

export function TradeDetail({ id }: { id: string }) {
  const router = useRouter();
  const tz = useTimeZone();
  const query = useTrade(id);
  const strategies = useStrategies();
  const update = useUpdateTrade(id);
  const remove = useDeleteTrade();
  const [closeOpen, setCloseOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (query.isPending) return <LoadingRows rows={6} />;
  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404;
    return (
      <ErrorState
        message={notFound ? "Ce trade n'existe pas ou a été supprimé." : "Impossible de charger le trade."}
        onRetry={notFound ? undefined : () => void query.refetch()}
      />
    );
  }

  const trade = query.data;
  const strategy = strategies.data?.results.find((s) => s.id === trade.strategy);
  const isOpen = trade.status === "OPEN";

  async function reopen() {
    try {
      await update.mutateAsync({ realized_rr: null });
      toast.success("Trade rouvert.");
    } catch {
      toast.error("Impossible de rouvrir le trade.");
    }
  }

  async function confirmDelete() {
    try {
      await remove.mutateAsync(trade.id);
      toast.success("Trade supprimé.");
      router.replace("/trades");
    } catch {
      toast.error("Suppression impossible.");
      setDeleteOpen(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Button asChild variant="ghost" size="sm" className="mb-3 -ml-2">
        <Link href="/trades">
          <ArrowLeft aria-hidden /> Journal
        </Link>
      </Button>

      <PageHeader
        title={trade.name}
        description={`${trade.asset} · ${MARKET_LABEL[trade.market_type]} · ${DIRECTION_LABEL[trade.direction]}`}
        actions={
          <>
            {isOpen ? (
              <Button onClick={() => setCloseOpen(true)}>
                <CheckCircle2 aria-hidden /> Clôturer
              </Button>
            ) : (
              <Button variant="outline" onClick={reopen} disabled={update.isPending}>
                <RotateCcw aria-hidden /> Rouvrir
              </Button>
            )}
            <Button asChild variant="outline">
              <Link href={`/trades/${trade.id}/edit`}>
                <Pencil aria-hidden /> Modifier
              </Link>
            </Button>
            <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
              <Trash2 aria-hidden /> Supprimer
            </Button>
          </>
        }
      />

      <Card className="mb-4">
        <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 pt-6">
          <div>
            <p className="text-xs text-muted-foreground">Statut</p>
            <StatusBadge status={trade.status} className="mt-1" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">RR réalisé</p>
            <RValue value={trade.realized_rr} className="text-2xl font-semibold" />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">RR prévu</p>
            <p className="tabular text-2xl font-semibold text-muted-foreground">{formatR(trade.planned_rr)}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Détails</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Item label="Date du trade">{formatDateTime(trade.trade_date, tz)}</Item>
            <Item label="Date de clôture">{formatDateTime(trade.closed_at, tz)}</Item>
            <Item label="Stratégie">
              {trade.strategy ? (strategy?.name ?? "—") : "Aucune"}
              {strategy && !strategy.is_active && (
                <span className="ml-2 text-xs text-muted-foreground">(désactivée)</span>
              )}
            </Item>
            <Item label="Prix d'entrée">
              <span className="tabular">{formatPrice(trade.entry_price)}</span>
            </Item>
            <Item label="Stop loss">
              <span className="tabular">{formatPrice(trade.stop_loss)}</span>
            </Item>
            <Item label="Take profit">
              <span className="tabular">{formatPrice(trade.take_profit)}</span>
            </Item>
          </dl>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Notes</CardTitle>
        </CardHeader>
        <CardContent>
          {trade.notes ? (
            <p className="text-sm whitespace-pre-wrap">{trade.notes}</p>
          ) : (
            <p className="text-sm text-muted-foreground">Aucune note.</p>
          )}
        </CardContent>
      </Card>

      <ScreenshotsSection tradeId={trade.id} />

      <CloseTradeDialog trade={trade} open={closeOpen} onOpenChange={setCloseOpen} />

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce trade ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {trade.name} » sera définitivement supprimé. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={confirmDelete} disabled={remove.isPending}>
              {remove.isPending ? "Suppression…" : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
