import type { ReactNode } from 'react';
import { useState } from 'react';
import type { Decorator, Preview } from '@storybook/nextjs-vite';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { initialize, mswLoader } from 'msw-storybook-addon';

import { ThemeProvider } from '../src/shared/providers/ThemeProvider';

import '../src/shared/styles/globals.css';

initialize({
  onUnhandledRequest: 'bypass',
});

function makeStorybookQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        staleTime: 1000 * 60,
        gcTime: 1000 * 60 * 5,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function StorybookProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeStorybookQueryClient);

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <div className="bg-fill-normal-normal text-text-normal-normal min-h-screen">{children}</div>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

const withCatchupProviders: Decorator = (Story) => (
  <StorybookProviders>
    <Story />
  </StorybookProviders>
);

const preview: Preview = {
  decorators: [withCatchupProviders],
  loaders: [mswLoader],
  parameters: {
    layout: 'fullscreen',
    nextjs: {
      appDirectory: true,
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
