'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import Error from '@/public/icons/icon/error.svg';
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from '@/shared/components/ui/dropdown-menu';
import { versionQueries } from '@/shared/queries/version.queries';

/**
 * 상단 More 버튼 드롭다운 메뉴를 렌더링
 */
export function MoreButtonContent() {
  const router = useRouter();
  const { data: version } = useQuery(versionQueries.current());

  return (
    <DropdownMenuContent
      align="end"
      sideOffset={6}
      className="flex w-62.5 flex-col gap-1 rounded-xl"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      <DropdownMenuItem onSelect={() => router.push('/mypage/help')}>
        <Error className="text-icon-normal-neutral h-6 w-6 shrink-0" />
        <span>도움말</span>
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <div className="text-label-xsmall text-text-normal-alternative flex items-center gap-2.5 px-2">
        <span>버전 기록</span>
        {version && <span>v{version}</span>}
      </div>
    </DropdownMenuContent>
  );
}
