"use client";

import { PageHeader } from "@/components/shared/page-header";
import { ErrorState, LoadingRows } from "@/components/shared/states";
import { ApiError } from "@/services/api-client";
import { useTrade } from "../hooks";
import { TradeForm } from "./trade-form";

export function TradeEdit({ id }: { id: string }) {
  const query = useTrade(id);

  if (query.isPending) return <LoadingRows rows={6} />;
  if (query.isError) {
    const notFound = query.error instanceof ApiError && query.error.status === 404;
    return (
      <ErrorState
        message={notFound ? "Ce trade n'existe pas." : "Impossible de charger le trade."}
        onRetry={notFound ? undefined : () => void query.refetch()}
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Modifier le trade" description={query.data.name} />
      {/* key : le formulaire repart des données serveur si le trade est rechargé */}
      <TradeForm key={query.data.updated_at} trade={query.data} />
    </div>
  );
}
