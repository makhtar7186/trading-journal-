import { z } from "zod";

/** Mêmes règles que le serveur (qui reste seul juge, y compris pour la robustesse du mot de passe). */
export const registerSchema = z
  .object({
    username: z
      .string()
      .trim()
      .min(3, "Au moins 3 caractères.")
      .max(150, "150 caractères maximum.")
      .regex(/^[\p{L}\p{N}_.@+-]+$/u, "Lettres, chiffres et @ . + - _ uniquement (pas d'espaces)."),
    email: z.string().trim().refine((v) => v === "" || z.email().safeParse(v).success, "Adresse e-mail invalide."),
    password: z.string().min(8, "Au moins 8 caractères."),
    password_confirm: z.string().min(1, "Confirmez le mot de passe."),
  })
  .refine((v) => v.password === v.password_confirm, {
    path: ["password_confirm"],
    message: "Les mots de passe ne correspondent pas.",
  });

export type RegisterValues = z.infer<typeof registerSchema>;
