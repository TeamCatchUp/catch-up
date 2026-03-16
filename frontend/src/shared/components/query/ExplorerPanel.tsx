'use client';

import { NoHistoryGuide } from '@/shared/components/query/guide/NoHistoryGuide';
import { RecentActivityExplorer } from '@/shared/components/query/recent/RecentActivityExplorer';

interface ExplorerPanelProps {
  variant?: 'default' | 'no-history';
  onExampleClick?: (query: string) => void;
}

export default function ExplorerPanel({ variant = 'default', onExampleClick }: ExplorerPanelProps) {
  if (variant === 'no-history') {
    return <NoHistoryGuide onExampleClick={onExampleClick} />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col items-start gap-2 self-stretch overflow-hidden">
      <RecentActivityExplorer />
    </div>
  );
}
