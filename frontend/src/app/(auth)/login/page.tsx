"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { LineChart } from "lucide-react";
import { z } from "zod";

import { FieldError } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/features/auth/api";
import { ME_KEY, useAuth } from "@/features/auth/auth-provider";
import { useRegistrationStatus } from "@/features/auth/use-registration-status";
import { ApiError } from "@/services/api-client";

const schema = z.object({
  username: z.string().trim().min(1, "Saisissez votre identifiant."),
  password: z.string().min(1, "Saisissez votre mot de passe."),
});
type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const registration = useRegistrationStatus();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function onSubmit(values: FormValues) {
    try {
      const me = await login(values.username, values.password);
      queryClient.setQueryData(ME_KEY, me);
      router.replace("/dashboard");
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Connexion impossible.";
      setError("root", { message });
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <LineChart className="size-5 text-primary" aria-hidden /> Trading Journal
          </div>
          <CardTitle>Connexion</CardTitle>
          <CardDescription>Accédez à votre journal de trading.</CardDescription>
        </CardHeader>
        <CardContent>
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
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                className="mt-1.5"
                {...register("password")}
              />
              <FieldError messages={errors.password?.message} />
            </div>
            <FieldError messages={errors.root?.message} />
            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? "Connexion…" : "Se connecter"}
            </Button>
          </form>
          {registration.data?.enabled && (
            <p className="mt-4 text-center text-sm text-muted-foreground">
              {registration.data.has_users ? "Pas encore de compte ? " : "Aucun compte n'existe encore. "}
              <Link href="/register" className="text-foreground underline underline-offset-4">
                Créer un compte
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
