import IconTagChannel from '@/public/icons/icon/tag_channel.svg';
import { cn } from '@/shared/utils/cn';

import type { OnboardingChannelRow } from '../../types/llmWikiOnboarding';
import { ONBOARDING_CHANNEL_TABLE_GRID } from './onboardingChannelTableGrid';

interface OnboardingChannelTableProps {
  headers: { name: string; lastModified: string };
  rows: readonly OnboardingChannelRow[];
}

// 온보딩 2단계 채널 표. 선택 표시·빈 목록·로딩은 시안에 없어 데이터 행만 그린다
export default function OnboardingChannelTable({ headers, rows }: OnboardingChannelTableProps) {
  return (
    <div className="overflow-x-auto">
      <table role="table" className="border-line-normal-neutral block min-w-fit overflow-hidden rounded-xl border">
        <thead role="rowgroup" className="block">
          <tr role="row" className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'border-line-normal-neutral border-b py-3')}>
            <th role="columnheader" className="text-label-xsmall text-text-normal-alternative text-left font-normal">
              {headers.name}
            </th>
            <th role="columnheader" className="text-label-xsmall text-text-normal-alternative text-right font-normal">
              {headers.lastModified}
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup" className="block">
          {rows.map((row) => (
            <tr key={row.channel.id} role="row" className={cn(ONBOARDING_CHANNEL_TABLE_GRID, 'py-3')}>
              <td role="cell" className="flex min-w-0 items-center gap-3">
                <span className="flex size-5 shrink-0 items-center justify-center">
                  <IconTagChannel className="text-icon-normal-neutral size-4" />
                </span>
                <span className="text-body-small text-text-normal-normal truncate">{row.channel.name}</span>
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
