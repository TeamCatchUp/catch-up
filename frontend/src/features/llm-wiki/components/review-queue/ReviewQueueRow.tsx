import IconAddSmall from '@/public/icons/icon/add_small.svg';
import DefaultProfileIcon from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error.svg';
import { cn } from '@/shared/utils/cn';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

import type { ReviewQueueItemData } from '../../types/llmWikiModel';

interface ReviewQueueRowProps {
  item: ReviewQueueItemData;
  selected?: boolean;
  onSelect?: (id: string) => void;
  /**
   * Figma "병합" 행(17762:102964)의 둘째 줄.
   *
   * 그 프레임의 레이어 이름이 "병합"이라 add_small + 들여쓴 줄은 병합 대상 문서로 읽히지만,
   * 둘째 줄이 병합될 문서 제목인지 묶인 하위 제안인지는 확정되지 않았다(감사: UNKNOWN).
   * 그래서 도메인 계약(ReviewQueueItemData)에 필드를 늘리지 않고 프레젠테이션 prop으로만 받는다.
   */
  secondaryTitle?: string;
}

/**
 * 검토 큐 좌측 목록(17564:126942)의 행.
 *
 * 신뢰도·유형 배지는 의도적으로 렌더하지 않는다 — 신뢰도는 감사 판정 MISSING(필터에만 있고 행에는 없다),
 * 유형은 백엔드 3종↔명세 6유형 불일치로 체계가 미정이다. 그래서 confidence·type을 props로 받지도 않는다.
 * hover 채움도 넣지 않았다: 비선택 행은 Figma에서 fills=[]이고 hover 정의가 없다.
 */
export default function ReviewQueueRow({ item, selected = false, onSelect, secondaryTitle }: ReviewQueueRowProps) {
  const { id, title, authorName, authorProfileImageUrl, waitingLabel, hasConflictIcon } = item;
  const safeProfileImageUrl = authorProfileImageUrl && isSafeUrl(authorProfileImageUrl) ? authorProfileImageUrl : null;

  // Figma는 제목 묶음을 한 겹 더 감싸지만(17762:105460) 바깥 gap과 안쪽 gap이 둘 다 12라 평평하게 폈다.
  // 높이 84는 결과값이다(12 + 23 + 12 + 25 + 12) — h-*로 못박지 않는다.
  return (
    <button
      type="button"
      aria-current={selected ? 'true' : undefined}
      onClick={() => onSelect?.(id)}
      className={cn(
        'border-line-normal-neutral flex w-full flex-col gap-3 border-b px-4 py-3 text-left',
        selected && 'bg-fill-normal-strong',
      )}
    >
      <span className="flex w-full min-w-0 items-center gap-3">
        {hasConflictIcon && <IconError aria-hidden className="text-accent-red-default size-6 shrink-0" />}
        <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{title}</span>
      </span>

      {secondaryTitle && (
        <span className="flex w-full min-w-0 items-center gap-3">
          {/* 칩 26 = padding 2 × 2 + 아이콘 22. 둘째 줄 들여쓰기는 이 칩 폭에서 나온다 */}
          <span className="bg-fill-normal-strong flex shrink-0 rounded-full p-0.5">
            <IconAddSmall aria-hidden className="text-icon-normal-neutral size-5.5" />
          </span>
          <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{secondaryTitle}</span>
        </span>
      )}

      <span className="text-body-xsmall flex w-full min-w-0 items-center gap-3">
        {/* 아바타 관례는 AgentCard와 같다 — 공용 컴포넌트가 없어 25px 원형 + 폴백 아이콘을 그대로 반복한다 */}
        <span className="border-line-normal-assistive flex size-6.25 shrink-0 items-center justify-center overflow-hidden rounded-xl border">
          {safeProfileImageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={safeProfileImageUrl} alt="" className="size-full object-cover" />
          ) : (
            <DefaultProfileIcon aria-hidden className="size-full" />
          )}
        </span>
        <span className="text-text-normal-normal min-w-0 flex-1 truncate">{authorName}</span>
        <span className="text-text-normal-assistive shrink-0">{waitingLabel}</span>
      </span>
    </button>
  );
}
