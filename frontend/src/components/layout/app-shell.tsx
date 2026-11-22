"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LineChart, LogOut, Menu, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useLogout } from "@/features/auth/use-logout";
import { useAuth } from "@/features/auth/auth-provider";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav-items";

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Navigation principale" className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 py-2.5 font-semibold">
      <LineChart className="size-5 text-primary" aria-hidden />
      Trading Journal
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const performLogout = useLogout();

  async function handleLogout() {
    await performLogout();
    toast.success("Vous êtes déconnecté.");
  }

  return (
    <div className="flex min-h-screen">
      {/* Lien d'évitement : visible uniquement au focus clavier */}
      <a
        href="#contenu"
        className="sr-only z-50 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Aller au contenu
      </a>
      {/* Barre latérale : tablette et desktop */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar p-4 md:flex">
        <div className="mb-6 px-2">
          <Brand />
        </div>
        <NavLinks />
        <div className="mt-auto border-t border-sidebar-border pt-4">
          <p className="truncate px-2 text-xs text-muted-foreground">{user?.username}</p>
          <Button variant="ghost" className="mt-2 w-full justify-start" onClick={handleLogout}>
            <LogOut aria-hidden /> Se déconnecter
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur md:px-8">
          {/* Menu : mobile */}
          <div className="md:hidden">
            <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Ouvrir le menu">
                  <Menu />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 bg-sidebar p-4">
                <SheetTitle className="mb-1">
                  <Brand />
                </SheetTitle>
                <SheetDescription className="sr-only">Navigation principale</SheetDescription>
                <div className="mt-4">
                  <NavLinks onNavigate={() => setMenuOpen(false)} />
                </div>
                <Button variant="ghost" className="mt-6 w-full justify-start" onClick={handleLogout}>
                  <LogOut aria-hidden /> Se déconnecter
                </Button>
              </SheetContent>
            </Sheet>
          </div>
          <div className="md:hidden">
            <Brand />
          </div>
          <div className="ml-auto hidden md:block">
            <Button asChild size="lg">
              <Link href="/trades/new">
                <Plus aria-hidden /> Ajouter un trade
              </Link>
            </Button>
          </div>
        </header>

        <main id="contenu" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 pb-24 outline-none md:px-8 md:pb-10">
          {children}
        </main>

        {/* Action principale toujours accessible sur mobile */}
        <Button
          asChild
          size="lg"
          className="fixed right-4 bottom-4 z-30 h-12 rounded-full px-5 shadow-lg md:hidden"
        >
          <Link href="/trades/new" aria-label="Ajouter un trade">
            <Plus aria-hidden /> Ajouter un trade
          </Link>
        </Button>
      </div>
    </div>
  );
}
