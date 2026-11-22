"use client";

import { useState } from "react";
import { Pencil, Plus, Power, PowerOff } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, ErrorState, LoadingRows } from "@/components/shared/states";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Strategy } from "@/types/api";
import { useDeactivateStrategy, useStrategies, useUpdateStrategy } from "../hooks";
import { StrategyDialog } from "./strategy-dialog";

export function StrategiesView() {
  const query = useStrategies();
  const update = useUpdateStrategy();
  const deactivate = useDeactivateStrategy();
  const [editing, setEditing] = useState<Strategy | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [toDeactivate, setToDeactivate] = useState<Strategy | null>(null);
  const [showInactive, setShowInactive] = useState(false);

  const all = query.data?.results ?? [];
  const visible = all.filter((s) => showInactive || s.is_active);
  const inactiveCount = all.filter((s) => !s.is_active).length;

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  async function reactivate(strategy: Strategy) {
    try {
      await update.mutateAsync({ id: strategy.id, payload: { is_active: true } });
      toast.success(`« ${strategy.name} » réactivée.`);
    } catch {
      toast.error("Réactivation impossible.");
    }
  }

  async function confirmDeactivate() {
    if (!toDeactivate) return;
    try {
      await deactivate.mutateAsync(toDeactivate.id);
      toast.success(`« ${toDeactivate.name} » désactivée.`);
    } catch {
      toast.error("Désactivation impossible.");
    }
    setToDeactivate(null);
  }

  return (
    <>
      <PageHeader
        title="Stratégies"
        description="Vos méthodes de trading. Une stratégie désactivée reste associée à ses anciens trades."
        actions={
          <Button onClick={openCreate}>
            <Plus aria-hidden /> Nouvelle stratégie
          </Button>
        }
      />

      {inactiveCount > 0 && (
        <label className="mb-4 flex w-fit items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="size-4 accent-primary"
          />
          Afficher les stratégies désactivées ({inactiveCount})
        </label>
      )}

      {query.isError ? (
        <ErrorState message="Impossible de charger les stratégies." onRetry={() => void query.refetch()} />
      ) : query.isPending ? (
        <LoadingRows rows={3} />
      ) : visible.length === 0 ? (
        <EmptyState
          title="Aucune stratégie"
          description="Créez une stratégie pour pouvoir l'associer à vos trades."
          action={
            <Button onClick={openCreate}>
              <Plus aria-hidden /> Nouvelle stratégie
            </Button>
          }
        />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {visible.map((strategy) => (
            <li key={strategy.id}>
              <Card className={strategy.is_active ? "" : "opacity-70"}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="min-w-0 truncate">{strategy.name}</CardTitle>
                    {!strategy.is_active && <Badge variant="outline">Désactivée</Badge>}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {strategy.description ? (
                    <p className="whitespace-pre-wrap">{strategy.description}</p>
                  ) : (
                    <p className="text-muted-foreground">Aucune description.</p>
                  )}
                  {strategy.entry_rules && (
                    <div>
                      <p className="text-xs text-muted-foreground">Entrée</p>
                      <p className="whitespace-pre-wrap">{strategy.entry_rules}</p>
                    </div>
                  )}
                  {strategy.exit_rules && (
                    <div>
                      <p className="text-xs text-muted-foreground">Sortie</p>
                      <p className="whitespace-pre-wrap">{strategy.exit_rules}</p>
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2 pt-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditing(strategy);
                        setDialogOpen(true);
                      }}
                    >
                      <Pencil aria-hidden /> Modifier
                    </Button>
                    {strategy.is_active ? (
                      <Button variant="ghost" size="sm" onClick={() => setToDeactivate(strategy)}>
                        <PowerOff aria-hidden /> Désactiver
                      </Button>
                    ) : (
                      <Button variant="ghost" size="sm" onClick={() => reactivate(strategy)}>
                        <Power aria-hidden /> Réactiver
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <StrategyDialog open={dialogOpen} onOpenChange={setDialogOpen} strategy={editing} />

      <AlertDialog open={!!toDeactivate} onOpenChange={(open) => !open && setToDeactivate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver cette stratégie ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {toDeactivate?.name} » ne sera plus proposée pour de nouveaux trades. Les trades existants
              la conservent, et vous pourrez la réactiver à tout moment.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeactivate}>Désactiver</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
