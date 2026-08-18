import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
import { cn } from '@/shared/utils/cn';

import type { OnboardingChannelListStatus, OnboardingChannelRow } from '../../types/llmWikiOnboarding';
import { ONBOARDING_CHANNEL_TABLE_GRID } from './onboardingChannelTableGrid';
import OnboardingChannelEmptyState from './states/OnboardingChannelEmptyState';
import OnboardingChannelErrorNotice from './states/OnboardingChannelErrorNotice';
import OnboardingChannelTableSkeleton from './states/OnboardingChannelTableSkeleton';

interface OnboardingChannelTableProps {
  headers: { name: string; lastModified: string };
  rows: readonly OnboardingChannelRow[];
  status?: OnboardingChannelListStatus;
  onRetry?: () => void;
}

// 온보딩 2단계 채널 표. 선택 표시는 시안에 없어 데이터 행만 그린다
export default function OnboardingChannelTable({
  headers,
  rows,
  status = 'ready',
  onRetry,
}: OnboardingChannelTableProps) {
  if (status === 'loading') return <OnboardingChannelTableSkeleton />;
  if (status === 'error') return <OnboardingChannelErrorNotice onRetry={onRetry} />;
  if (rows.length === 0) return <OnboardingChannelEmptyState />;

  return (
    <div className="overflow-x-auto">
      <table role="table" className="border-line-normal-neutral block min-w-fit overflow-hidden rounded-xl border">
        <thead role="rowgroup" className="block">
          <tr role="row" className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'border-line-normal-neutral h-9 border-b')}>
            {/* 머리글은 아이콘 자리(22+12)만큼 들여써 행의 채널명과 x가 맞는다 */}
            <th
              role="columnheader"
              className="text-body-xsmall text-text-normal-alternative pl-8.5 text-left font-medium"
            >
              {headers.name}
            </th>
            <th role="columnheader" className="text-body-xsmall text-text-normal-alternative text-right font-medium">
              {headers.lastModified}
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup" className="block">
          {rows.map((row) => (
            <tr key={row.channel.id} role="row" className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'py-3')}>
              <td role="cell" className="flex min-w-0 items-center gap-3">
                <IconTagChannel className="text-icon-normal-neutral size-5.5 shrink-0" />
                <span className="text-body-small text-text-normal-neutral truncate">{row.channel.name}</span>
              </td>
              <td role="cell" className="text-body-small text-text-normal-alternative text-right">
                {row.lastModifiedLabel}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
