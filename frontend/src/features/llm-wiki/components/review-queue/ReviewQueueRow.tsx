import IconAddSmall from '@/public/icons/icon/add_small.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { AvatarGroup } from '@/shared/components/ui/avatar-group';
import { cn } from '@/shared/utils/cn';

import type { ReviewQueueRowData } from '../../api/knowledgeReviewMappers';
import type { DocumentOwner } from '../../types/llmWikiModel';

interface ReviewQueueRowProps {
  /** 목록 응답 한 줄. baseRevisionId는 상세에서만 오므로 행 계약에 없다 */
  item: ReviewQueueRowData;
  selected?: boolean;
  onSelect?: (id: string) => void;
  /**
   * 병합 행의 둘째 줄. 의미가 미확정이라 도메인 계약에 필드를 늘리지 않고
   * 프레젠테이션 prop으로만 받는다.
   */
  secondaryTitle?: string;
}

/** 담당자 표기 3갈래 — 없음(기본 아바타+문구) / 1인(아바타+이름) / 2인 이상(스택+"외 N명" 요약). */
function OwnerDisplay({ owners }: { owners: readonly DocumentOwner[] }) {
  if (owners.length === 0) {
    return (
      <>
        <Avatar size="small" className="border-line-normal-assistive rounded-xl" />
        <span className="text-body-xsmall text-text-normal-assistive truncate">담당자 없음</span>
      </>
    );
  }

  if (owners.length === 1) {
    return (
      <>
        <Avatar size="small" src={owners[0].profileImageUrl} className="border-line-normal-assistive rounded-xl" />
        <span className="text-body-xsmall text-text-normal-neutral truncate">{owners[0].displayName}</span>
      </>
    );
  }

  return (
    <>
      <AvatarGroup avatars={owners.map((owner) => ({ src: owner.profileImageUrl }))} size="small" max={3} />
      <span className="text-body-xsmall text-text-normal-neutral truncate">
        {owners[0].displayName}님 외 {owners.length - 1}명
      </span>
    </>
  );
}

/**
 * 검토 큐 좌측 목록의 행. 충돌(모순) 아이콘은 MVP 제외라 렌더하지 않는다.
 * 작성자·신뢰도·유형은 큐 응답에 없거나 시안 근거가 없어 렌더하지 않는다.
 */
export default function ReviewQueueRow({ item, selected = false, onSelect, secondaryTitle }: ReviewQueueRowProps) {
  const { id, title, owners, waitingLabel } = item;

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

      <span className="flex w-full min-w-0 items-center gap-3">
        <span className="flex min-w-0 flex-1 items-center gap-3">
          <OwnerDisplay owners={owners} />
        </span>
        <span className="text-body-xsmall text-text-normal-assistive shrink-0">{waitingLabel}</span>
      </span>
    </button>
  );
}
