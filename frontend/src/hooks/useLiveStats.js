import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client.js";

const summaryDefaults = {
  queryKey: ["summary"],
  queryFn: () => api.summary(),
  refetchInterval: 3000,
  staleTime: 0,
  structuralSharing: false,
};

const healthDefaults = {
  queryKey: ["health"],
  queryFn: () => api.health(),
  refetchInterval: 4000,
  staleTime: 0,
  structuralSharing: false,
};

/** Shared options so every subscriber sees the same polling + freshness behavior. */
export function useSummaryQuery(overrides = {}) {
  return useQuery({ ...summaryDefaults, ...overrides });
}

export function useHealthQuery(overrides = {}) {
  return useQuery({ ...healthDefaults, ...overrides });
}
