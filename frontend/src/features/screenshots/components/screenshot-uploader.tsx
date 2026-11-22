"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { AlertCircle, CheckCircle2, ImagePlus, Loader2, Upload, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CATEGORY_OPTIONS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { ScreenshotCategory } from "@/types/api";
import { ACCEPTED_TYPES, MAX_FILE_BYTES, uploadErrorMessage } from "../api";
import { useUploadScreenshot } from "../hooks";

type ItemStatus = "ready" | "uploading" | "error";

interface QueueItem {
  id: string;
  file: File;
  previewUrl: string | null;
  category: ScreenshotCategory;
  status: ItemStatus;
  progress: number;
  error?: string;
  /** Refusé avant envoi (format/taille) : ne sera pas transmis. */
  rejected: boolean;
}

const acceptedTypes: readonly string[] = ACCEPTED_TYPES;
let counter = 0;

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} Mo` : `${Math.max(1, Math.round(bytes / 1024))} Ko`;
}

function toQueueItem(file: File, category: ScreenshotCategory): QueueItem {
  const base = { id: `q${++counter}`, file, category, progress: 0 };
  if (!acceptedTypes.includes(file.type)) {
    return { ...base, previewUrl: null, status: "error", rejected: true, error: "Format non pris en charge (PNG, JPEG ou WebP)." };
  }
  const previewUrl = URL.createObjectURL(file);
  if (file.size > MAX_FILE_BYTES) {
    return { ...base, previewUrl, status: "error", rejected: true, error: `Fichier trop volumineux (maximum ${formatSize(MAX_FILE_BYTES)}).` };
  }
  return { ...base, previewUrl, status: "ready", rejected: false };
}

export function ScreenshotUploader({ tradeId }: { tradeId: string }) {
  const upload = useUploadScreenshot(tradeId);
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [defaultCategory, setDefaultCategory] = useState<ScreenshotCategory>("BEFORE");
  const [sending, setSending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  // Libère les aperçus (URL d'objets) au démontage.
  useEffect(
    () => () => {
      itemsRef.current.forEach((item) => item.previewUrl && URL.revokeObjectURL(item.previewUrl));
    },
    [],
  );

  const addFiles = useCallback(
    (files: FileList | File[]) => {
      const added = Array.from(files).map((file) => toQueueItem(file, defaultCategory));
      if (added.length) setItems((current) => [...current, ...added]);
    },
    [defaultCategory],
  );

  function patchItem(id: string, patch: Partial<QueueItem>) {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function removeItem(id: string) {
    setItems((current) => {
      const target = current.find((item) => item.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return current.filter((item) => item.id !== id);
    });
  }

  async function sendAll() {
    const queue = itemsRef.current.filter((item) => !item.rejected && item.status !== "uploading");
    if (queue.length === 0) return;
    setSending(true);
    let succeeded = 0;
    for (const item of queue) {
      patchItem(item.id, { status: "uploading", progress: 0, error: undefined });
      try {
        await upload.mutateAsync({
          file: item.file,
          category: item.category,
          onProgress: (progress) => patchItem(item.id, { progress }),
        });
        succeeded += 1;
        removeItem(item.id);
      } catch (error) {
        patchItem(item.id, { status: "error", error: uploadErrorMessage(error) });
      }
    }
    setSending(false);
    const failed = queue.length - succeeded;
    if (succeeded) toast.success(`${succeeded} capture${succeeded > 1 ? "s" : ""} ajoutée${succeeded > 1 ? "s" : ""}.`);
    if (failed) toast.error(`${failed} fichier${failed > 1 ? "s" : ""} non envoyé${failed > 1 ? "s" : ""}.`);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  }

  const sendable = items.filter((item) => !item.rejected).length;

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-3 rounded-xl border border-dashed px-4 py-6 text-center transition-colors",
          dragging ? "border-primary bg-primary/10" : "border-border",
        )}
      >
        <ImagePlus className="size-7 text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Glissez vos captures ici ou sélectionnez-les (PNG, JPEG, WebP — {formatSize(MAX_FILE_BYTES)} max chacune).
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <input
            ref={inputRef}
            id="screenshot-files"
            type="file"
            multiple
            accept={ACCEPTED_TYPES.join(",")}
            className="sr-only"
            aria-label="Sélectionner des captures d'écran"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = ""; // permet de re-sélectionner le même fichier
            }}
          />
          <Button type="button" variant="outline" onClick={() => inputRef.current?.click()}>
            <Upload aria-hidden /> Choisir des fichiers
          </Button>
          <div className="flex items-center gap-2 text-sm">
            <label htmlFor="default-category" className="text-muted-foreground">
              Catégorie des nouveaux fichiers
            </label>
            <Select value={defaultCategory} onValueChange={(v) => setDefaultCategory(v as ScreenshotCategory)}>
              <SelectTrigger id="default-category" size="sm" className="w-28">
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
        </div>
      </div>

      {items.length > 0 && (
        <>
          <ul className="space-y-2" aria-label="Fichiers à envoyer">
            {items.map((item) => (
              <li key={item.id} className="flex items-center gap-3 rounded-lg border border-border bg-card p-2">
                {item.previewUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element -- aperçu local (blob:), pas une image servie
                  <img
                    src={item.previewUrl}
                    alt={`Aperçu de ${item.file.name}`}
                    onError={() => patchItem(item.id, { previewUrl: null })}
                    className="size-14 shrink-0 rounded-md object-cover"
                  />
                ) : (
                  <div className="flex size-14 shrink-0 items-center justify-center rounded-md bg-muted" aria-hidden>
                    <AlertCircle className="size-5 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatSize(item.file.size)}</p>
                  {item.status === "uploading" && (
                    <div className="mt-1.5 flex items-center gap-2">
                      <div
                        role="progressbar"
                        aria-label={`Envoi de ${item.file.name}`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={item.progress}
                        className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
                      >
                        <div className="h-full bg-primary transition-[width]" style={{ width: `${item.progress}%` }} />
                      </div>
                      <span className="tabular w-9 text-right text-xs text-muted-foreground">{item.progress}%</span>
                    </div>
                  )}
                  {item.status === "error" && (
                    <p role="alert" className="mt-1 flex items-start gap-1 text-xs text-negative">
                      <AlertCircle className="mt-0.5 size-3 shrink-0" aria-hidden /> {item.error}
                    </p>
                  )}
                </div>
                {!item.rejected && (
                  <Select
                    value={item.category}
                    onValueChange={(v) => patchItem(item.id, { category: v as ScreenshotCategory })}
                    disabled={item.status === "uploading"}
                  >
                    <SelectTrigger size="sm" className="w-28 shrink-0" aria-label={`Catégorie de ${item.file.name}`}>
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
                )}
                {item.status === "uploading" ? (
                  <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" aria-label="Envoi en cours" />
                ) : (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Retirer ${item.file.name}`}
                    onClick={() => removeItem(item.id)}
                  >
                    <X />
                  </Button>
                )}
              </li>
            ))}
          </ul>
          <div className="flex justify-end">
            <Button type="button" onClick={sendAll} disabled={sending || sendable === 0}>
              {sending ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden /> Envoi…
                </>
              ) : (
                <>
                  <CheckCircle2 aria-hidden /> Envoyer {sendable} fichier{sendable > 1 ? "s" : ""}
                </>
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
