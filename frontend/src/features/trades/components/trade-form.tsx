"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";

import { FieldError } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useTimeZone } from "@/features/auth/auth-provider";
import { useStrategies } from "@/features/strategies/hooks";
import { DIRECTION_OPTIONS, MARKET_OPTIONS } from "@/lib/labels";
import { ApiError } from "@/services/api-client";
import type { Trade } from "@/types/api";
import { useCreateTrade, useUpdateTrade } from "../hooks";
import {
  defaultFormValues,
  NO_STRATEGY,
  toPayload,
  tradeFormSchema,
  tradeToFormValues,
  type TradeFormValues,
} from "../schemas";

function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <Label htmlFor={htmlFor}>{label}</Label>
      <div className="mt-1.5">{children}</div>
      {hint && !error && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      <FieldError messages={error} />
    </div>
  );
}

export function TradeForm({ trade }: { trade?: Trade }) {
  const router = useRouter();
  const tz = useTimeZone();
  const create = useCreateTrade();
  const update = useUpdateTrade(trade?.id ?? "");
  const strategies = useStrategies();

  const initial = useMemo(
    () => (trade ? tradeToFormValues(trade, tz) : defaultFormValues(tz)),
    [trade, tz],
  );

  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<TradeFormValues>({
    resolver: zodResolver(tradeFormSchema),
    defaultValues: initial,
  });

  // Stratégies actives, plus celle déjà rattachée au trade même si elle a été désactivée.
  const strategyOptions = (strategies.data?.results ?? []).filter(
    (s) => s.is_active || s.id === trade?.strategy,
  );

  async function onSubmit(values: TradeFormValues) {
    const payload = toPayload(values, tz);
    try {
      const saved = trade ? await update.mutateAsync(payload) : await create.mutateAsync(payload);
      toast.success(trade ? "Trade mis à jour." : "Trade enregistré.");
      router.push(`/trades/${saved.id}`);
    } catch (error) {
      if (error instanceof ApiError) {
        let mapped = false;
        for (const [field, messages] of Object.entries(error.fieldErrors)) {
          if (field in tradeFormSchema.shape) {
            setError(field as FieldPath<TradeFormValues>, { message: messages.join(" ") });
            mapped = true;
          }
        }
        toast.error(mapped ? "Corrigez les champs signalés." : error.message);
      } else {
        toast.error("Enregistrement impossible.");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-8">
      <section aria-labelledby="sec-general" className="space-y-4">
        <h2 id="sec-general" className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Général
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Nom du trade" htmlFor="name" error={errors.name?.message}>
              <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
            </Field>
          </div>
          <Field
            label="Date et heure"
            htmlFor="trade_date"
            hint={`Fuseau d'affichage : ${tz}`}
            error={errors.trade_date?.message}
          >
            <Input
              id="trade_date"
              type="datetime-local"
              aria-invalid={!!errors.trade_date}
              {...register("trade_date")}
            />
          </Field>
          <Field label="Actif" htmlFor="asset" hint="Ex. EURUSD, XAUUSD, NAS100, BTCUSD" error={errors.asset?.message}>
            <Input id="asset" autoCapitalize="characters" aria-invalid={!!errors.asset} {...register("asset")} />
          </Field>
          <Field label="Marché" htmlFor="market_type" error={errors.market_type?.message}>
            <Controller
              control={control}
              name="market_type"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="market_type" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MARKET_OPTIONS.map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
          <Field label="Sens" htmlFor="direction" error={errors.direction?.message}>
            <Controller
              control={control}
              name="direction"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="direction" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DIRECTION_OPTIONS.map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Stratégie" htmlFor="strategy" error={errors.strategy?.message}>
              <Controller
                control={control}
                name="strategy"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="strategy" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_STRATEGY}>Aucune</SelectItem>
                      {strategyOptions.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                          {s.is_active ? "" : " (désactivée)"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>
        </div>
      </section>

      <section aria-labelledby="sec-risk" className="space-y-4">
        <h2 id="sec-risk" className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Risque et résultat
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="RR prévu"
            htmlFor="planned_rr"
            hint="Strictement positif (ex. 2,5). Facultatif."
            error={errors.planned_rr?.message}
          >
            <Input id="planned_rr" inputMode="decimal" aria-invalid={!!errors.planned_rr} {...register("planned_rr")} />
          </Field>
          <Field
            label="RR réalisé"
            htmlFor="realized_rr"
            hint="Laisser vide = trade ouvert. Le statut (gagnant, perdant, break-even) est déterminé automatiquement."
            error={errors.realized_rr?.message}
          >
            <Input
              id="realized_rr"
              inputMode="decimal"
              placeholder="ex. 2,5 ou -1"
              aria-invalid={!!errors.realized_rr}
              {...register("realized_rr")}
            />
          </Field>
          <Field label="Prix d'entrée" htmlFor="entry_price" error={errors.entry_price?.message}>
            <Input id="entry_price" inputMode="decimal" aria-invalid={!!errors.entry_price} {...register("entry_price")} />
          </Field>
          <Field label="Stop loss" htmlFor="stop_loss" error={errors.stop_loss?.message}>
            <Input id="stop_loss" inputMode="decimal" aria-invalid={!!errors.stop_loss} {...register("stop_loss")} />
          </Field>
          <Field label="Take profit" htmlFor="take_profit" error={errors.take_profit?.message}>
            <Input id="take_profit" inputMode="decimal" aria-invalid={!!errors.take_profit} {...register("take_profit")} />
          </Field>
        </div>
      </section>

      <section aria-labelledby="sec-notes" className="space-y-4">
        <h2 id="sec-notes" className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Notes
        </h2>
        <Field label="Pourquoi ce trade ? Leçons ?" htmlFor="notes" error={errors.notes?.message}>
          <Textarea id="notes" rows={5} {...register("notes")} />
        </Field>
      </section>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button asChild variant="outline" size="lg">
          <Link href={trade ? `/trades/${trade.id}` : "/trades"}>Annuler</Link>
        </Button>
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Enregistrement…" : trade ? "Enregistrer les modifications" : "Enregistrer le trade"}
        </Button>
      </div>
    </form>
  );
}
