"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";

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
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/services/api-client";
import type { Strategy } from "@/types/api";
import { useCreateStrategy, useUpdateStrategy } from "../hooks";

const schema = z.object({
  name: z.string().trim().min(1, "Le nom est obligatoire.").max(120, "120 caractères maximum."),
  description: z.string(),
  entry_rules: z.string(),
  exit_rules: z.string(),
});
type FormValues = z.infer<typeof schema>;

const EMPTY: FormValues = { name: "", description: "", entry_rules: "", exit_rules: "" };

export function StrategyDialog({
  open,
  onOpenChange,
  strategy,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategy?: Strategy | null;
}) {
  const create = useCreateStrategy();
  const update = useUpdateStrategy();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: EMPTY });

  // Recharge les valeurs à chaque ouverture (création ou édition d'une autre stratégie).
  useEffect(() => {
    if (open) {
      reset(
        strategy
          ? {
              name: strategy.name,
              description: strategy.description,
              entry_rules: strategy.entry_rules,
              exit_rules: strategy.exit_rules,
            }
          : EMPTY,
      );
    }
  }, [open, strategy, reset]);

  async function onSubmit(values: FormValues) {
    try {
      if (strategy) await update.mutateAsync({ id: strategy.id, payload: values });
      else await create.mutateAsync(values);
      toast.success(strategy ? "Stratégie mise à jour." : "Stratégie créée.");
      onOpenChange(false);
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors.name) {
        setError("name", { message: error.fieldErrors.name.join(" ") });
      } else {
        toast.error(error instanceof ApiError ? error.message : "Enregistrement impossible.");
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          <DialogHeader>
            <DialogTitle>{strategy ? "Modifier la stratégie" : "Nouvelle stratégie"}</DialogTitle>
            <DialogDescription>
              Décrivez votre méthode pour pouvoir comparer ses résultats plus tard.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label htmlFor="s-name">Nom</Label>
            <Input id="s-name" className="mt-1.5" aria-invalid={!!errors.name} {...register("name")} />
            <FieldError messages={errors.name?.message} />
          </div>
          <div>
            <Label htmlFor="s-desc">Description</Label>
            <Textarea id="s-desc" rows={3} className="mt-1.5" {...register("description")} />
          </div>
          <div>
            <Label htmlFor="s-entry">Règles d&apos;entrée</Label>
            <Textarea id="s-entry" rows={3} className="mt-1.5" {...register("entry_rules")} />
          </div>
          <div>
            <Label htmlFor="s-exit">Règles de sortie</Label>
            <Textarea id="s-exit" rows={3} className="mt-1.5" {...register("exit_rules")} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Annuler
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
