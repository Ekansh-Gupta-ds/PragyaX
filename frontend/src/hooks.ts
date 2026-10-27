import { useCallback, useEffect, useState } from "react";
import { parseHashRoute, navigate as routerNavigate, useAppRouter } from "./routes/router";

export { useAppRouter, routerNavigate as navigate };

/**
 * Backward-compatible useHashRoute hook:
 * returns [path, param] (e.g. ["result", "atm_1"])
 */
export function useHashRoute(): [string, string | undefined] {
  const [current, setCurrent] = useState(parseHashRoute);

  useEffect(() => {
    const onChange = () => setCurrent(parseHashRoute());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return [current.path, current.param];
}

/** Load data on mount with loading / error state and a reload function. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
