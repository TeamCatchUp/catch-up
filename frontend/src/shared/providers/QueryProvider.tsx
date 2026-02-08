'use client';

import { useState } from 'react';
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { AxiosError } from 'axios';

function makeQueryClient() {
  const queryClient: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (query.state.data !== undefined) {
          console.error(`Background update failed: ${error.message}`);
        }
      },
    }),
    mutationCache: new MutationCache({
      onSuccess: (_data, _variables, _context, mutation) => {
        const invalidates = mutation.meta?.invalidates as string[][] | undefined;
        if (invalidates) {
          invalidates.forEach((key) => {
            queryClient.invalidateQueries({ queryKey: key });
          });
        } else {
          queryClient.invalidateQueries();
        }
      },
      onError: (error, _variables, _context, mutation) => {
        if (mutation.meta?.skipGlobalErrorHandler) return;
        console.error(`Mutation failed: ${error.message}`);
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60,
        gcTime: 1000 * 60 * 5,
        retry: (failureCount, error) => {
          if (
            error instanceof AxiosError &&
            error.response?.status &&
            error.response.status >= 400 &&
            error.response.status < 500
          ) {
            return false;
          }
          return failureCount < 2;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
  return queryClient;
}

export default function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}
