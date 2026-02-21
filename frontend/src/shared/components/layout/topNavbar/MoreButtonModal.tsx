'use client';

import { useRouter } from 'next/navigation';

import { DropdownMenuContent, DropdownMenuItem } from '@/shared/components/ui/dropdown-menu';

import Error from '/public/icons/icon/error.svg';

/**
 * 상단 More 버튼 드롭다운 메뉴를 렌더링
 */
export function MoreButtonContent() {
  const router = useRouter();

  return (
    <DropdownMenuContent
      align="end"
      sideOffset={6}
      className="flex w-[250px] flex-col gap-1 rounded-xl"
      onCloseAutoFocus={(e) => e.preventDefault()}
    >
      <DropdownMenuItem onSelect={() => router.push('/mypage/help')}>
        <Error className="h-6 w-6 shrink-0 text-gray-50" />
        <span>도움말</span>
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}
