"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { updateMe } from "@/features/auth/api";
import { useLogout } from "@/features/auth/use-logout";
import { ME_KEY, useAuth } from "@/features/auth/auth-provider";
import { formatDateTime, listTimeZones } from "@/lib/datetime";
import { ApiError } from "@/services/api-client";

export function SettingsView() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const zones = useMemo(() => listTimeZones(), []);
  const handleLogout = useLogout();

  if (!user) return null;
  const timezone = draft ?? user.timezone;
  const dirty = timezone !== user.timezone;

  async function save() {
    setSaving(true);
    try {
      const updated = await updateMe({ timezone });
      queryClient.setQueryData(ME_KEY, updated);
      setDraft(null);
      toast.success("Fuseau horaire enregistré.");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Enregistrement impossible.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Paramètres" />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Profil</CardTitle>
          <CardDescription>Le compte est géré par l&apos;administrateur (pas d&apos;inscription publique).</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted-foreground">Identifiant</dt>
              <dd className="mt-0.5 text-sm">{user.username}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">E-mail</dt>
              <dd className="mt-0.5 text-sm">{user.email || "—"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>Affichage</CardTitle>
          <CardDescription>
            Thème sombre par défaut. Le fuseau horaire sert à afficher et saisir les dates des trades.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label htmlFor="tz">Fuseau horaire</Label>
            <Select value={timezone} onValueChange={setDraft}>
              <SelectTrigger id="tz" className="mt-1.5 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="max-h-72">
                {zones.map((zone) => (
                  <SelectItem key={zone} value={zone}>
                    {zone}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="mt-1 text-xs text-muted-foreground">
              Il est actuellement : {formatDateTime(new Date().toISOString(), timezone)}
            </p>
          </div>
          <Button onClick={save} disabled={!dirty || saving}>
            {saving ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={handleLogout}>
            <LogOut aria-hidden /> Se déconnecter
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
