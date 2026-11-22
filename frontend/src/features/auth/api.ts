import { apiFetch } from "@/services/api-client";
import type { User } from "@/types/api";

export const fetchMe = () => apiFetch<User>("/auth/me/");

export async function login(username: string, password: string): Promise<User> {
  // Pose le cookie CSRF avant le POST de connexion (exigé côté serveur).
  await apiFetch<void>("/auth/csrf/");
  return apiFetch<User>("/auth/login/", { method: "POST", body: { username, password } });
}

export const logout = () => apiFetch<void>("/auth/logout/", { method: "POST" });

export interface RegistrationStatus {
  enabled: boolean;
  has_users: boolean;
}

/** La création de compte est-elle proposée ? (désactivée par défaut ; locale uniquement côté serveur) */
export const getRegistrationStatus = () => apiFetch<RegistrationStatus>("/auth/registration/");

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  timezone: string;
}

export async function registerAccount(payload: RegisterPayload): Promise<User> {
  await apiFetch<void>("/auth/csrf/"); // cookie CSRF exigé par le serveur
  return apiFetch<User>("/auth/register/", { method: "POST", body: payload });
}

export const updateMe =(data: Partial<Pick<User, "timezone">>) =>
  apiFetch<User>("/auth/me/", { method: "PATCH", body: data });
