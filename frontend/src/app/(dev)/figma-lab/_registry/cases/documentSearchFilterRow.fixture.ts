import type { DateRange } from 'react-day-picker';

import type { DocsSource } from '@/shared/types/source';

export interface DocumentSearchFilterRowFixture {
  selectedSources: DocsSource[];
  dateRange: DateRange | undefined;
  smartFilter: boolean;
}

export const documentSearchFilterRowFixture = {
  entryDefault: {
    selectedSources: [],
    dateRange: undefined,
    smartFilter: true,
  },
  entrySelected: {
    selectedSources: ['github', 'slack'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: true,
  },
  resultExpanded: {
    selectedSources: ['github', 'channel_talk', 'confluence'] satisfies DocsSource[],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: false,
  },
  sourceDropdownOpen: {
    selectedSources: ['github', 'channel_talk', 'confluence', 'jira', 'slack'] satisfies DocsSource[],
    dateRange: undefined,
    smartFilter: true,
  },
  datePickerOpen: {
    selectedSources: [],
    dateRange: {
      from: new Date(2026, 3, 7),
      to: new Date(2026, 3, 20),
    },
    smartFilter: true,
  },
} satisfies Record<string, DocumentSearchFilterRowFixture>;
