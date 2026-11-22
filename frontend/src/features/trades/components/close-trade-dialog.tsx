"use client";

import { useState } from "react";
import { toast } from "sonner";

import { FieldError } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { decimalSign } from "@/lib/format";
import { STATUS_LABEL } from "@/lib/labels";
import { ApiError } from "@/services/api-client";
import type { Trade } from "@/types/api";
import { useUpdateTrade } from "../hooks";
import { normalizeDecimal } from "../schemas";

export function CloseTradeDialog({
  trade,
  open,
  onOpenChange,
}: {
  trade: Trade;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const update = useUpdateTrade(trade.id);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const normalized = normalizeDecimal(value);
    if (decimalSign(normalized) === null) {
      setError("Saisissez un nombre (ex. 2,5 ; -1 ; 0).");
      return;
    }
    setError(null);
    try {
      const saved = await update.mutateAsync({ realized_rr: normalized });
      toast.success(`Trade clôturé : ${STATUS_LABEL[saved.status]}.`);
      setValue("");
      onOpenChange(false);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? (e.fieldErrors.realized_rr?.join(" ") ?? e.message)
          : "Clôture impossible.",
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form onSubmit={submit} noValidate>
          <DialogHeader>
            <DialogTitle>Clôturer le trade</DialogTitle>
            <DialogDescription>
              Saisissez le RR réalisé. Le statut est déterminé automatiquement : positif = gagnant,
              négatif = perdant, zéro = break-even.
            </DialogDescription>
          </DialogHeader>
          <div className="my-4">
            <Label htmlFor="close-rr">RR réalisé</Label>
            <Input
              id="close-rr"
              inputMode="decimal"
              autoFocus
              className="mt-1.5"
              placeholder="ex. 2,5 ou -1"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              aria-invalid={!!error}
            />
            <FieldError messages={error ?? undefined} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Clôture…" : "Clôturer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
