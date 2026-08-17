import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import type { TagItem } from '../../types/llmWikiModel';

interface TagNavigationListProps {
  tags: readonly TagItem[];
  /** 선택된 태그. 우측 문서 목록이 어느 태그의 것인지를 이 값이 정한다. */
  selectedTagId?: string;
  onTagClick?: (tagId: string) => void;
}

/**
 * 태그 탐색 목록. 그룹 머리글 없이 평평하게 나열한다 — 태그 계층 구조는 범위 밖이다.
 * 문서 건수·hover 채움은 시안 근거가 없어 렌더하지 않는다.
 */
export default function TagNavigationList({ tags, selectedTagId, onTagClick }: TagNavigationListProps) {
  // 폭·높이는 2단 레이아웃의 열이 갖는 값이라 여기 박지 않는다 — 슬롯이 준다.
  return (
    <ul className="border-line-normal-neutral flex h-full flex-col gap-4 overflow-y-auto border-r p-5">
      {tags.map((tag) => {
        const selected = tag.id === selectedTagId;

        return (
          <li key={tag.id} className="shrink-0">
            <button
              type="button"
              aria-current={selected ? 'true' : undefined}
              onClick={() => onTagClick?.(tag.id)}
              className={cn(
                'text-heading-small flex h-6 w-full items-center gap-3 text-left',
                selected ? 'text-text-primary-assistive' : 'text-text-normal-alternative',
              )}
            >
              <span className="min-w-0 flex-1 truncate">{tag.name}</span>
              {/* 아이콘 색은 텍스트와 같은 값이지만 토큰 계열이 달라 명시한다 */}
              <IconArrowRight2
                aria-hidden
                className={cn('size-6 shrink-0', selected ? 'text-icon-primary-assistive' : 'text-icon-normal-neutral')}
              />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
