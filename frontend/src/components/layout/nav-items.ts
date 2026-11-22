import {
  BarChart3,
  CalendarDays,
  LayoutDashboard,
  Lightbulb,
  NotebookText,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trades", label: "Journal des trades", icon: NotebookText },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/calendar", label: "Calendrier", icon: CalendarDays },
  { href: "/strategies", label: "Stratégies", icon: Lightbulb },
  { href: "/settings", label: "Paramètres", icon: Settings },
];
