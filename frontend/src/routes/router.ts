import { useCallback, useEffect, useState } from "react";
import type { ParsedRoute, RoutePath } from "../types/routes";
import { ROUTE_TITLES } from "./navigation";

const DEFAULT_ROUTE: RoutePath = "dashboard";

/**
 * Parses window.location.hash into a typed RoutePath and optional param.
 * Supports patterns:
 *   "#/chat" -> { path: "chat", fullPath: "/chat" }
 *   "#/result/atm_1" -> { path: "result", param: "atm_1", fullPath: "/result/atm_1" }
 */
export function parseHashRoute(): ParsedRoute {
  const hash = window.location.hash.replace(/^#\/?/, "").trim();
  const segments = hash.split("/").filter(Boolean);
  const rawPath = segments[0] as RoutePath | undefined;
  const param = segments[1];

  const validPaths: RoutePath[] = [
    "dashboard",
    "chat",
    "subjects",
    "assessment",
    "results",
    "result",
    "challenge",
  ];

  const path = rawPath && validPaths.includes(rawPath) ? rawPath : DEFAULT_ROUTE;

  return {
    path,
    param,
    fullPath: `/${segments.join("/")}`,
  };
}

export function navigate(path: RoutePath | string, param?: string) {
  const target = param ? `/${path}/${param}` : `/${path}`;
  if (window.location.hash !== `#${target}`) {
    window.location.hash = target;
  }
}

export function useAppRouter() {
  const [current, setCurrent] = useState<ParsedRoute>(parseHashRoute);

  useEffect(() => {
    const handleHashChange = () => {
      const parsed = parseHashRoute();
      setCurrent(parsed);
      const title = ROUTE_TITLES[parsed.path] ?? "Learning Platform";
      document.title = `PragyaX — ${title}`;
    };

    // Initialize title
    const initialTitle = ROUTE_TITLES[current.path] ?? "Learning Platform";
    document.title = `PragyaX — ${initialTitle}`;

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [current.path]);

  const isActive = useCallback(
    (targetPath: RoutePath) => {
      if (current.path === "result" && targetPath === "results") return true;
      return current.path === targetPath;
    },
    [current.path]
  );

  return {
    route: current.path,
    param: current.param,
    navigate,
    isActive,
  };
}
