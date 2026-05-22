'use client';

// 원문 패널 상단 — 대화 제목 + 안전한 '원문 열기' 외부 링크.

import OpenInNew from '@/public/icons/icon/open_in_new.svg';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface OriginalPanelHeaderProps {
  title: string;
  url: string | null;
}

export default function OriginalPanelHeader({ title, url }: OriginalPanelHeaderProps) {
  const displayTitle = title.trim() ? title : '제목 없음';
  const canOpen = isSafeUrl(url);

  return (
    <header className="border-edge-neutral flex w-full items-center gap-2 border-b px-5 py-4">
      <h2 className="text-heading-small text-content-normal min-w-0 flex-1 truncate font-semibold">
        {displayTitle}
      </h2>
      {canOpen && url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-body-xsmall text-content-primary hover:bg-fill-primary-interaction-hover-assistive flex shrink-0 items-center gap-1 rounded-full px-2 py-1 font-medium transition-colors"
        >
          <OpenInNew className="h-4 w-4" />
          <span>원문 열기</span>
        </a>
      )}
    </header>
  );
}
