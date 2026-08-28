import type { ReactNode } from 'react';

import { Avatar } from '@/shared/components/ui/avatar';

interface WikiSpaceTitleBlockProps {
  /** 제목 앞 아이콘 — 채널·폴더 화면이 서로 다른 걸 주입한다 */
  icon: ReactNode;
  name: string;
  /** 작성자 표시명. 값이 없으면 줄 자체를 그리지 않는다 — 채널에는 대응 필드가 없다 */
  authorName?: string;
  authorProfileImageUrl?: string | null;
}

/** 채널·폴더 페이지 상단의 이름·작성자 블록. 페이지 헤더(breadcrumb 바)와는 다른 층위다. */
export default function WikiSpaceTitleBlock({
  icon,
  name,
  authorName,
  authorProfileImageUrl,
}: WikiSpaceTitleBlockProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-5">
        <span className="bg-fill-normal-strong text-icon-normal-alternative flex shrink-0 rounded-lg p-2 [&_svg]:size-6">
          {icon}
        </span>
        <h1 className="text-heading-xlarge text-text-normal-strong min-w-0 flex-1 truncate">{name}</h1>
      </div>

      {authorName && (
        <div className="flex items-center gap-3">
          {/* 이름이 바로 옆이라 아바타 alt는 비운다(중복 낭독 방지) */}
          <Avatar
            size="small"
            src={authorProfileImageUrl}
            className="border-line-normal-assistive shrink-0 rounded-xl"
          />
          <span className="text-body-xsmall text-text-normal-alternative">작성자</span>
          <span className="text-body-xsmall text-text-normal-neutral">{authorName}</span>
        </div>
      )}
    </div>
  );
}
