import type { ReactNode } from 'react';
import { useState } from 'react';
import type { Decorator, Preview } from '@storybook/nextjs-vite';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { initialize, mswLoader } from 'msw-storybook-addon';

import Toast from '../src/shared/components/ui/toast';
import { TooltipProvider } from '../src/shared/components/ui/tooltip';
import { ThemeProvider } from '../src/shared/providers/ThemeProvider';

import '../src/shared/styles/globals.css';

initialize({
  onUnhandledRequest(request, print) {
    if (new URL(request.url).pathname.startsWith('/api/')) {
      print.error();
    }
  },
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
        <TooltipProvider delayDuration={200}>
          <div className="bg-fill-normal-normal text-text-normal-normal min-h-screen">{children}</div>
          <Toast />
        </TooltipProvider>
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
    // Flows(여정 문서)를 사이드바 맨 위로. Flows 안은 여정 순서(커넥터 연결 → 이용자 매핑)로 고정한다
    // — 임포트 순서 등 암묵적 정렬에 맡기지 않고, 여정 순서를 명시적으로 고정하기 위해서다.
    options: {
      storySort: {
        order: ['Flows', ['커넥터 연결', '임베딩', '이용자 매핑'], 'Screens', 'Compositions', 'Primitives'],
      },
    },
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
