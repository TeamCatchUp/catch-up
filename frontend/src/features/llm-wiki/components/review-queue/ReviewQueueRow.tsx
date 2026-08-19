import IconAddSmall from '@/public/icons/icon/add_small.svg';
import { cn } from '@/shared/utils/cn';

import type { ReviewQueueItemData } from '../../types/llmWikiModel';

interface ReviewQueueRowProps {
  item: ReviewQueueItemData;
  selected?: boolean;
  onSelect?: (id: string) => void;
  /**
   * 병합 행의 둘째 줄. 의미가 미확정이라 도메인 계약에 필드를 늘리지 않고
   * 프레젠테이션 prop으로만 받는다.
   */
  secondaryTitle?: string;
}

/**
 * 검토 큐 좌측 목록의 행. 충돌(모순) 아이콘은 MVP 제외라 렌더하지 않는다.
 * 작성자·신뢰도·유형은 큐 응답에 없거나 시안 근거가 없어 렌더하지 않는다.
 */
export default function ReviewQueueRow({ item, selected = false, onSelect, secondaryTitle }: ReviewQueueRowProps) {
  const { id, title, waitingLabel } = item;

  // 행 높이는 결과값이다 — h-*로 못박지 않는다.
  return (
    <button
      type="button"
      aria-current={selected ? 'true' : undefined}
      onClick={() => onSelect?.(id)}
      className={cn(
        'border-line-normal-neutral hover:bg-fill-normal-interaction-hover flex w-full cursor-pointer flex-col gap-3 border-b px-4 py-3 text-left transition-colors',
        selected && 'bg-fill-normal-strong',
      )}
    >
      <span className="flex w-full min-w-0 items-center gap-3">
        <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{title}</span>
      </span>

      {secondaryTitle && (
        <span className="flex w-full min-w-0 items-center gap-3">
          {/* 둘째 줄 들여쓰기는 이 칩 폭에서 나온다 */}
          <span className="bg-fill-normal-strong flex shrink-0 rounded-full p-0.5">
            <IconAddSmall aria-hidden className="text-icon-normal-neutral size-5.5" />
          </span>
          <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{secondaryTitle}</span>
        </span>
      )}

      <span className="text-body-xsmall text-text-normal-assistive w-full truncate">{waitingLabel}</span>
    </button>
  );
}
