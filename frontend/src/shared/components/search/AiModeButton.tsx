'use client';

// 문서 검색 입력 옆의 "AI 모드" 전환 버튼.
// expanded일 때 mousedown을 막아 패널이 닫히지 않게 한다.

import IconAi from '@/public/icons/icon/ai.svg';

interface AiModeButtonProps {
  expanded: boolean;
  onClick: () => void;
}

export default function AiModeButton({ expanded, onClick }: AiModeButtonProps) {
  return (
    <button
      type="button"
      onMouseDown={(e) => expanded && e.preventDefault()}
      onClick={onClick}
      className="bg-fill-primary-normal-neutral text-text-primary-normal flex h-10 shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 transition-colors"
    >
      <IconAi aria-hidden className="size-5" />
      <span className="text-body-small font-medium whitespace-nowrap">AI 모드</span>
    </button>
  );
}
