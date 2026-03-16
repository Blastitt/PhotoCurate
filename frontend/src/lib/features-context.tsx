"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { features as featuresApi, type FeaturesResponse } from "@/lib/api";

interface FeaturesContextValue {
  features: FeaturesResponse | null;
  loading: boolean;
}

const FeaturesContext = createContext<FeaturesContextValue>({
  features: null,
  loading: true,
});

export function FeaturesProvider({ children }: { children: ReactNode }) {
  const [features, setFeatures] = useState<FeaturesResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    featuresApi
      .get()
      .then(setFeatures)
      .catch(() => setFeatures(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <FeaturesContext.Provider value={{ features, loading }}>
      {children}
    </FeaturesContext.Provider>
  );
}

export function useFeatures() {
  return useContext(FeaturesContext);
}
