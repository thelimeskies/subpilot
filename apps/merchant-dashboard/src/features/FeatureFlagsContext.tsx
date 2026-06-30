import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { api, isApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export interface FeatureFlagCatalogEntry {
  key: string;
  label: string;
  description: string;
  default: boolean;
}

export type FeatureFlagMap = Record<string, boolean>;

interface FeatureBundle {
  flags: FeatureFlagMap;
  catalog: FeatureFlagCatalogEntry[];
}

interface FeatureFlagsContextValue {
  flags: FeatureFlagMap;
  catalog: FeatureFlagCatalogEntry[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  /**
   * Resolve a single flag. Returns `true` while the bundle is still loading so
   * controls do not flicker in/out during the initial fetch. Server-side
   * enforcement is the authoritative gate; this hook only hides/disables UI.
   */
  isEnabled: (key: string) => boolean;
}

const FeatureFlagsContext = createContext<FeatureFlagsContextValue | undefined>(undefined);

const EMPTY_FLAGS: FeatureFlagMap = {};
const EMPTY_CATALOG: FeatureFlagCatalogEntry[] = [];

export function FeatureFlagsProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const [flags, setFlags] = useState<FeatureFlagMap>(EMPTY_FLAGS);
  const [catalog, setCatalog] = useState<FeatureFlagCatalogEntry[]>(EMPTY_CATALOG);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (status !== "authenticated") {
      setFlags(EMPTY_FLAGS);
      setCatalog(EMPTY_CATALOG);
      setLoaded(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body = await api.get<FeatureBundle>("/me/features");
      setFlags(body.flags ?? EMPTY_FLAGS);
      setCatalog(body.catalog ?? EMPTY_CATALOG);
      setLoaded(true);
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load feature flags.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const isEnabled = useCallback(
    (key: string) => {
      // Optimistic: while we haven't received the bundle yet, assume the flag
      // is on so controls do not flash hidden during the initial fetch. The
      // server is the real gate; a 403 from the API surfaces the disabled
      // reason if we get the optimistic guess wrong.
      if (!loaded) return true;
      const value = flags[key];
      return value === undefined ? true : value;
    },
    [loaded, flags]
  );

  const value = useMemo<FeatureFlagsContextValue>(
    () => ({ flags, catalog, loading, error, reload, isEnabled }),
    [flags, catalog, loading, error, reload, isEnabled]
  );

  return <FeatureFlagsContext.Provider value={value}>{children}</FeatureFlagsContext.Provider>;
}

export function useFeatureFlags() {
  const ctx = useContext(FeatureFlagsContext);
  if (!ctx) throw new Error("useFeatureFlags must be used inside <FeatureFlagsProvider>");
  return ctx;
}
