import {
  BookOpen,
  ClipboardCheck,
  History,
  LayoutDashboard,
  MessageSquare,
  Zap,
} from "lucide-react";
import type { NavItem, RoutePath } from "../types/routes";

export const NAVIGATION_ITEMS: readonly NavItem[] = [
  {
    path: "dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    category: "core",
    description: "Overview of your learning progress, mastery, and recommended topics",
  },
  {
    path: "chat",
    label: "Learning Chat",
    icon: MessageSquare,
    category: "core",
    description: "Interactive AI tutor for programming concepts and practical code guidance",
  },
  {
    path: "subjects",
    label: "Subjects",
    icon: BookOpen,
    category: "core",
    description: "Browse and select available course tracks and learning domains",
  },
  {
    path: "assessment",
    label: "Assessment",
    icon: ClipboardCheck,
    category: "practice",
    description: "Evaluate your practical understanding with server-evaluated assessments",
  },
  {
    path: "challenge",
    label: "Daily Challenge",
    icon: Zap,
    category: "practice",
    description: "Daily bite-sized coding puzzle to build consistent problem-solving habits",
  },
  {
    path: "results",
    label: "My Results",
    icon: History,
    category: "records",
    description: "Detailed performance history and topic-level mastery reports",
  },
] as const;

export const ROUTE_TITLES: Record<RoutePath, string> = {
  dashboard: "Dashboard",
  chat: "Learning Chat",
  subjects: "Choose Subject",
  assessment: "Assessment",
  challenge: "Daily Challenge",
  results: "My Results",
  result: "Assessment Review",
};
