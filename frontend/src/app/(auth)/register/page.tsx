"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm, type FieldPath } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { LineChart } from "lucide-react";

import { FieldError, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { registerAccount } from "@/features/auth/api";
import { ME_KEY, useAuth } from "@/features/auth/auth-provider";
import { registerSchema, type RegisterValues } from "@/features/auth/schemas";
import { useRegistrationStatus } from "@/features/auth/use-registration-status";
import { isValidTimeZone } from "@/lib/datetime";
import { ApiError } from "@/services/api-client";

const FIELDS = ["username", "email", "password", "password_confirm"] as const;

function browserTimeZone(): string {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return zone && isValidTimeZone(zone) ? zone : "UTC";
}

export default function RegisterPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const status = useRegistrationStatus();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { username: "", email: "", password: "", password_confirm: "" },
  });

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function onSubmit(values: RegisterValues) {
    try {
      const me = await registerAccount({
        ...values,
        username: values.username.trim(),
        email: values.email.trim(),
        timezone: browserTimeZone(),
      });
      queryClient.setQueryData(ME_KEY, me);
      router.replace("/dashboard");
    } catch (error) {
      if (!(error instanceof ApiError)) {
        setError("root", { message: "Création impossible." });
        return;
      }
      let mapped = false;
      for (const [field, messages] of Object.entries(error.fieldErrors)) {
        if ((FIELDS as readonly string[]).includes(field)) {
          setError(field as FieldPath<RegisterValues>, { message: messages.join(" ") });
          mapped = true;
        }
      }
      if (!mapped) setError("root", { message: error.message });
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <LineChart className="size-5 text-primary" aria-hidden /> Trading Journal
          </div>
          <CardTitle>Créer un compte</CardTitle>
          <CardDescription>
            {status.data && !status.data.has_users
              ? "Bienvenue ! Créez votre compte pour commencer."
              : "Vos données restent sur cet ordinateur."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status.isPending ? (
            <LoadingRows rows={3} />
          ) : !status.data?.enabled ? (
            <div role="alert" className="space-y-3 text-sm">
              <p>La création de compte n&apos;est pas disponible ici.</p>
              <p className="text-muted-foreground">
                Elle n&apos;est proposée que depuis l&apos;ordinateur qui héberge l&apos;application.
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link href="/login">Retour à la connexion</Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
              <div>
                <Label htmlFor="username">Identifiant</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  autoFocus
                  aria-invalid={!!errors.username}
                  className="mt-1.5"
                  {...register("username")}
                />
                <FieldError messages={errors.username?.message} />
              </div>
              <div>
                <Label htmlFor="email">E-mail (facultatif)</Label>
                <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} className="mt-1.5" {...register("email")} />
                <FieldError messages={errors.email?.message} />
              </div>
              <div>
                <Label htmlFor="password">Mot de passe</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  aria-invalid={!!errors.password}
                  aria-describedby="password-hint"
                  className="mt-1.5"
                  {...register("password")}
                />
                <p id="password-hint" className="mt-1 text-xs text-muted-foreground">
                  8 caractères minimum, pas trop courant, pas uniquement des chiffres.
                </p>
                <FieldError messages={errors.password?.message} />
              </div>
              <div>
                <Label htmlFor="password_confirm">Confirmer le mot de passe</Label>
                <Input
                  id="password_confirm"
                  type="password"
                  autoComplete="new-password"
                  aria-invalid={!!errors.password_confirm}
                  className="mt-1.5"
                  {...register("password_confirm")}
                />
                <FieldError messages={errors.password_confirm?.message} />
              </div>
              <FieldError messages={errors.root?.message} />
              <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
                {isSubmitting ? "Création…" : "Créer mon compte"}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                Déjà un compte ?{" "}
                <Link href="/login" className="text-foreground underline underline-offset-4">
                  Se connecter
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
