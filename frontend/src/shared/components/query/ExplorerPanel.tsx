'use client';

import { RecentActivityExplorer } from '@/shared/components/query/recent/RecentActivityExplorer';

export default function ExplorerPanel() {
  return (
    <div className="no-scrollbar flex min-h-0 flex-1 flex-col items-start gap-2 self-stretch overflow-y-auto">
      <RecentActivityExplorer />
    </div>
  );
}
