import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { cn } from '@/shared/utils/cn';

import type { TagItem } from '../../types/llmWikiModel';

interface TagCategoryListProps {
  tags: readonly TagItem[];
  /** 선택된 태그. 우측 문서 목록이 어느 태그의 것인지를 이 값이 정한다. */
  selectedTagId?: string;
  onTagClick?: (tagId: string) => void;
}

/**
 * 대시보드 "태그 카테고리" 영역(17757:57635) 2단 탐색의 좌측 목록(17762:103078).
 *
 * 이름은 영역 이름을 따르지만 계층 목록이 아니다 — 그룹 머리글 없이 태그를 평평하게 나열한다.
 * MVP 명세 §11이 "태그 계층 구조"를 범위 밖으로 명시했고, 8/7 Figma 재확인에서도 8행 전부
 * 같은 구조(텍스트 fill + arrow_right2 24)였다.
 *
 * 문서 건수(TagItem.documentCount)는 렌더하지 않는다 — 시안 행에 건수 자리가 없다.
 * 태그 자동 부여·신설 UI도 만들지 않는다(명세 "추후 논의", 영역 헤더 소관).
 * hover 채움도 없다 — Figma 행 노드에 fills와 hover 정의가 둘 다 없다.
 */
export default function TagCategoryList({ tags, selectedTagId, onTagClick }: TagCategoryListProps) {
  // 폭 280·높이 300은 2단 레이아웃에서 열이 갖는 값이라 여기 박지 않는다 — 슬롯이 준다.
  // 우측 구분선은 노드 자신의 stroke다(strokeWeight "0px 1px 0px 0px").
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
              {/* 아이콘 색은 텍스트와 같은 값이지만 토큰 계열이 달라 명시한다(Icon/* vs Text/*) */}
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
