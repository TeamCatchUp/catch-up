import type { DateRange } from 'react-day-picker';

import type { SearchHistoryEntry } from '@/shared/types/searchHistory';
import type { DocsSource } from '@/shared/types/source';

export interface ResultSearchBarFixture {
  value: string;
  chips: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
  draftSmartFilter: boolean;
  historyEntries?: SearchHistoryEntry[];
  historyLoading?: boolean;
}

export const resultSearchBarFixture = {
  appliedCollapsed: {
    value: '지난주 결제 문서',
    chips: ['github', 'jira'] satisfies DocsSource[],
    dateRange: undefined,
    smartFilter: true,
    draftSmartFilter: true,
  },
  expandedDraft: {
    value: '이번 주 컨플루언스 문서',
    chips: ['confluence'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: true,
    draftSmartFilter: true,
    historyEntries: [
      {
        id: 'figma-lab-history-1',
        query: '이번 주 컨플루언스 문서',
        createdAt: new Date(2026, 4, 29, 9, 0, 0),
      },
      {
        id: 'figma-lab-history-2',
        query: '지난주 결제 승인 슬랙',
        createdAt: new Date(2026, 4, 28, 14, 30, 0),
      },
    ],
    historyLoading: false,
  },
} satisfies Record<string, ResultSearchBarFixture>;
