import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconError from '@/public/icons/icon/error.svg';
import { Avatar } from '@/shared/components/ui/avatar';
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
 * 검토 큐 좌측 목록의 행.
 * 신뢰도·유형·hover 채움은 시안 근거가 없어 렌더하지 않는다 — props로 받지도 않는다.
 */
export default function ReviewQueueRow({ item, selected = false, onSelect, secondaryTitle }: ReviewQueueRowProps) {
  const { id, title, authorName, authorProfileImageUrl, waitingLabel, hasConflictIcon } = item;

  // 행 높이는 결과값이다 — h-*로 못박지 않는다.
  return (
    <button
      type="button"
      aria-current={selected ? 'true' : undefined}
      onClick={() => onSelect?.(id)}
      className={cn(
        'border-line-normal-neutral flex w-full cursor-pointer flex-col gap-3 border-b px-4 py-3 text-left',
        selected && 'bg-fill-normal-strong',
      )}
    >
      <span className="flex w-full min-w-0 items-center gap-3">
        {hasConflictIcon && <IconError aria-hidden className="text-accent-red-default size-6 shrink-0" />}
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

      <span className="text-body-xsmall flex w-full min-w-0 items-center gap-3">
        {/* 공용 Avatar에 이 화면만의 radius·링을 덮어씌운다.
            alt를 비우는 이유는 옆에 작성자명이 이미 있어서다(중복 낭독 방지). */}
        <Avatar size="small" src={authorProfileImageUrl} className="border-line-normal-assistive rounded-xl" />
        <span className="text-text-normal-normal min-w-0 flex-1 truncate">{authorName}</span>
        <span className="text-text-normal-assistive shrink-0">{waitingLabel}</span>
      </span>
    </button>
  );
}
