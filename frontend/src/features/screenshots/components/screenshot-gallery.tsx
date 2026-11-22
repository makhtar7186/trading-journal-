"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, ImageOff, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTimeZone } from "@/features/auth/auth-provider";
import { formatDateTime } from "@/lib/datetime";
import { CATEGORY_LABEL, CATEGORY_OPTIONS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { Screenshot, ScreenshotCategory } from "@/types/api";
import { useDeleteScreenshot, useScreenshots, useUpdateScreenshot } from "../hooks";

type Filter = "ALL" | ScreenshotCategory;

function altText(shot: Screenshot): string {
  return shot.description || `Capture ${CATEGORY_LABEL[shot.category].toLowerCase()} — ${shot.original_filename}`;
}

function Thumb({ shot, className }: { shot: Screenshot; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className={cn("flex items-center justify-center bg-muted text-muted-foreground", className)}>
        <ImageOff className="size-6" aria-label="Image indisponible" />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- fichier privé servi par l'API (cookie de session)
    <img
      src={shot.file_url}
      alt={altText(shot)}
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn("object-cover", className)}
    />
  );
}

function Lightbox({
  shots,
  index,
  onIndexChange,
  onClose,
}: {
  shots: Screenshot[];
  index: number | null;
  onIndexChange: (index: number) => void;
  onClose: () => void;
}) {
  const tz = useTimeZone();
  const open = index !== null && shots[index] !== undefined;
  const current = open ? shots[index as number] : null;

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "ArrowRight") onIndexChange(Math.min((index as number) + 1, shots.length - 1));
      if (event.key === "ArrowLeft") onIndexChange(Math.max((index as number) - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, index, shots.length, onIndexChange]);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[95vh] w-[calc(100vw-1rem)] max-w-5xl gap-3 p-3 sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2 pr-8 text-base">
            {current && <Badge variant="outline">{CATEGORY_LABEL[current.category]}</Badge>}
            <span className="truncate">{current?.original_filename}</span>
            <span className="text-xs font-normal text-muted-foreground tabular">
              {open ? `${(index as number) + 1} / ${shots.length}` : ""}
            </span>
          </DialogTitle>
          <DialogDescription className="sr-only">
            Capture en grand format. Flèches gauche et droite pour naviguer, Échap pour fermer.
          </DialogDescription>
        </DialogHeader>
        {current && (
          <div className="relative flex min-h-0 items-center justify-center rounded-lg bg-black/40">
            {/* key : force le rechargement de l'image à chaque navigation */}
            <Thumb key={current.id} shot={current} className="max-h-[70vh] w-full object-contain" />
            <Button
              variant="secondary"
              size="icon"
              className="absolute left-2 top-1/2 -translate-y-1/2"
              aria-label="Capture précédente"
              disabled={(index as number) === 0}
              onClick={() => onIndexChange((index as number) - 1)}
            >
              <ChevronLeft />
            </Button>
            <Button
              variant="secondary"
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2"
              aria-label="Capture suivante"
              disabled={(index as number) === shots.length - 1}
              onClick={() => onIndexChange((index as number) + 1)}
            >
              <ChevronRight />
            </Button>
          </div>
        )}
        {current && (
          <p className="text-sm text-muted-foreground">
            {current.description || "Aucune description."}{" "}
            <span className="text-xs">· Ajoutée le {formatDateTime(current.uploaded_at, tz)}</span>
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function EditForm({ shot, tradeId, onClose }: { shot: Screenshot; tradeId: string; onClose: () => void }) {
  const update = useUpdateScreenshot(tradeId);
  // Initialisé depuis la capture ; le composant est remonté (key) pour chaque capture éditée.
  const [category, setCategory] = useState<ScreenshotCategory>(shot.category);
  const [description, setDescription] = useState(shot.description);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    try {
      await update.mutateAsync({ id: shot.id, category, description: description.trim() });
      toast.success("Capture mise à jour.");
      onClose();
    } catch {
      toast.error("Modification impossible.");
    }
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <DialogHeader>
        <DialogTitle>Modifier la capture</DialogTitle>
        <DialogDescription>{shot.original_filename}</DialogDescription>
      </DialogHeader>
      <div>
        <Label htmlFor="edit-category">Catégorie</Label>
        <Select value={category} onValueChange={(v) => setCategory(v as ScreenshotCategory)}>
          <SelectTrigger id="edit-category" className="mt-1.5 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div>
        <Label htmlFor="edit-description">Description</Label>
        <Input
          id="edit-description"
          className="mt-1.5"
          maxLength={500}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Annuler
        </Button>
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? "Enregistrement…" : "Enregistrer"}
        </Button>
      </DialogFooter>
    </form>
  );
}

function EditDialog({ shot, tradeId, onClose }: { shot: Screenshot | null; tradeId: string; onClose: () => void }) {
  return (
    <Dialog open={shot !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>{shot && <EditForm key={shot.id} shot={shot} tradeId={tradeId} onClose={onClose} />}</DialogContent>
    </Dialog>
  );
}

export function ScreenshotGallery({ tradeId }: { tradeId: string }) {
  const query = useScreenshots(tradeId);
  const remove = useDeleteScreenshot(tradeId);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  const [editing, setEditing] = useState<Screenshot | null>(null);
  const [deleting, setDeleting] = useState<Screenshot | null>(null);

  if (query.isPending) return <LoadingRows rows={2} />;
  if (query.isError) {
    return <ErrorState message="Impossible de charger les captures." onRetry={() => void query.refetch()} />;
  }

  const all = query.data;
  if (all.length === 0) {
    return (
      <EmptyState
        title="Aucune capture"
        description="Ajoutez des captures d'écran avant, pendant ou après le trade pour garder la trace de votre analyse."
      />
    );
  }

  const shown = filter === "ALL" ? all : all.filter((s) => s.category === filter);
  const count = (category: Filter) => (category === "ALL" ? all.length : all.filter((s) => s.category === category).length);

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await remove.mutateAsync(deleting.id);
      toast.success("Capture supprimée.");
    } catch {
      toast.error("Suppression impossible.");
    }
    setDeleting(null);
  }

  return (
    <>
      <div role="tablist" aria-label="Filtrer par catégorie" className="mb-3 flex flex-wrap gap-2">
        {(["ALL", ...CATEGORY_OPTIONS.map(([value]) => value)] as Filter[]).map((value) => (
          <Button
            key={value}
            role="tab"
            aria-selected={filter === value}
            size="sm"
            variant={filter === value ? "default" : "outline"}
            onClick={() => setFilter(value)}
          >
            {value === "ALL" ? "Toutes" : CATEGORY_LABEL[value]} ({count(value)})
          </Button>
        ))}
      </div>

      {shown.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Aucune capture dans cette catégorie.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {shown.map((shot, index) => (
            <li key={shot.id} className="group relative overflow-hidden rounded-lg border border-border bg-card">
              <button
                type="button"
                onClick={() => setViewerIndex(index)}
                aria-label={`Agrandir : ${altText(shot)}`}
                className="block w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Thumb shot={shot} className="aspect-video w-full" />
              </button>
              <div className="flex items-center justify-between gap-1 p-2">
                <Badge variant="outline">{CATEGORY_LABEL[shot.category]}</Badge>
                <div className="flex">
                  <Button variant="ghost" size="icon-sm" aria-label={`Modifier ${shot.original_filename}`} onClick={() => setEditing(shot)}>
                    <Pencil />
                  </Button>
                  <Button variant="ghost" size="icon-sm" aria-label={`Supprimer ${shot.original_filename}`} onClick={() => setDeleting(shot)}>
                    <Trash2 />
                  </Button>
                </div>
              </div>
              {shot.description && (
                <p className="truncate px-2 pb-2 text-xs text-muted-foreground" title={shot.description}>
                  {shot.description}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      <Lightbox shots={shown} index={viewerIndex} onIndexChange={setViewerIndex} onClose={() => setViewerIndex(null)} />
      <EditDialog shot={editing} tradeId={tradeId} onClose={() => setEditing(null)} />

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette capture ?</AlertDialogTitle>
            <AlertDialogDescription>
              « {deleting?.original_filename} » sera définitivement supprimée, fichier compris. Cette action est irréversible.
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
    </>
  );
}
