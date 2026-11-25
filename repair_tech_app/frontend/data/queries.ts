/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * Reads and writes, over TanStack Query.
 *
 * Reads are `facade(method, params)`: a query keyed by the facade and its
 * arguments, typed end to end from the Python signature. The cache persists
 * to IndexedDB, so the app opens offline on what it last knew; reads run
 * offline-first and refetch when the network or the screen comes back.
 *
 * Writes are `useFacadeMutation(method)`. They never queue offline: a timer
 * started when the request finally lands would start at the wrong time, so
 * a write without a network fails at once and says so. Every write returns
 * the fresh state of what it changed; that goes straight into the cache, and
 * whatever else is on screen refetches.
 */
import {createAsyncStoragePersister} from "@tanstack/query-async-storage-persister";
import {
  MutationCache,
  QueryClient,
  queryOptions,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {del, get, set} from "idb-keyval";
import {RpcError} from "../api/client";
import {MODEL, odoo, type Facade, type FacadeParams, type FacadeResult} from "./odoo";

export function facade<F extends Facade>(method: F, params: FacadeParams<F>) {
  return queryOptions({
    queryKey: [MODEL, method, params] as const,
    queryFn: ({signal}): Promise<FacadeResult<F>> =>
      odoo.with({signal}).invoke(MODEL, method, params),
  });
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      networkMode: "offlineFirst",
      staleTime: 15_000,
      gcTime: 7 * 24 * 3_600_000,
      // A refused call (a rule, access) won't change by asking again.
      retry: (count, error) =>
        !(error instanceof RpcError && error.isUserFacing) && count < 2,
    },
    mutations: {networkMode: "always", retry: false},
  },
  mutationCache: new MutationCache({
    onSettled: () =>
      queryClient.invalidateQueries({queryKey: [MODEL], refetchType: "active"}),
  }),
});

export const persister = createAsyncStoragePersister({
  storage: {
    getItem: (key: string) => get<string>(key),
    setItem: (key: string, value: string) => set(key, value),
    removeItem: (key: string) => del(key),
  },
  key: "repair-tech-app",
  throttleTime: 2_000,
});

/** The cache is dropped when a new build may read it differently. */
export const CACHE_BUSTER = import.meta.env.MODE + "-1";

export interface FacadeMutationOptions<F extends Facade> {
  /** Put the result where it belongs in the cache, before the refetches. */
  onSuccess?: (result: FacadeResult<F>, params: FacadeParams<F>) => void;
}

export function useFacadeMutation<F extends Facade>(
  method: F,
  options: FacadeMutationOptions<F> = {}
) {
  return useMutation<FacadeResult<F>, unknown, FacadeParams<F>>({
    mutationKey: [MODEL, method],
    mutationFn: (params) => odoo.invoke(MODEL, method, params),
    ...(options.onSuccess
      ? {onSuccess: (result, params) => options.onSuccess?.(result, params)}
      : {}),
  });
}

/** Put a facade's answer in the cache as if `method(params)` had been read. */
export function useCacheWriter() {
  const client = useQueryClient();
  return <F extends Facade>(
    method: F,
    params: FacadeParams<F>,
    value: FacadeResult<F>
  ): void => {
    client.setQueryData(facade(method, params).queryKey, value);
  };
}
