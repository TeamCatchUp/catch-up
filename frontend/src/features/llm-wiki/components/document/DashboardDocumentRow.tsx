import { Fragment } from 'react';

import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import IconFileFilled from '@/public/icons/icon/file_filled.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { cn } from '@/shared/utils/cn';

import type { BreadcrumbKind, DocumentRowData } from '../../types/llmWikiModel';
import DocumentStatusBadge from './DocumentStatusBadge';

/**
 * 대시보드 문서 표(17606:149822)의 열 템플릿.
 *
 * Figma 행은 좌/우 두 덩어리가 각각 fill이라 1040 - 패딩 12 - gap 16 = 1012를 506씩 나눠 갖는데,
 * 우측 506 = 194 + 16 + 184 + 16 + 96이므로 4열로 펴도 값이 같다(1028 - gap 48 - 474 = 506).
 * 고정폭 3개는 행끼리·헤더와 열을 맞추기 위한 것이다 — 표 헤더가 생기면 이 상수를 함께 쓴다.
 */
export const DASHBOARD_DOCUMENT_ROW_GRID =
  'grid grid-cols-[minmax(0,1fr)_194px_184px_96px] items-center gap-4 rounded-lg p-1.5';

// Figma가 아이콘을 정의한 breadcrumb 종류는 채널·폴더 2종뿐이다.
// 미지 종류는 아이콘을 발명하지 않고 라벨만 렌더한다(DocumentStatusBadge와 같은 규칙).
const BREADCRUMB_ICON: Partial<Record<BreadcrumbKind, typeof IconWikiChannel>> = {
  channel: IconWikiChannel,
  folder: IconFolder,
};

interface DashboardDocumentRowProps {
  document: DocumentRowData;
  onClick?: (id: string) => void;
}

export default function DashboardDocumentRow({ document, onClick }: DashboardDocumentRowProps) {
  const { id, title, breadcrumbs, status, hasConflictIcon, tags, lastActivityLabel } = document;
  const [visibleTag, ...collapsedTags] = tags;

  // 충돌 행은 선두 아이콘만 갈린다(17762:103348 #FFFAFA/#FF6363 vs 17762:102512 #F7F7F8/#B1B8BE).
  const LeadingIcon = hasConflictIcon ? IconErrorFilled : IconFileFilled;

  // Figma 행 프레임은 fills=[]라 hover 채움이 정의되어 있지 않다 — 시각을 발명하지 않는다.
  return (
    <button type="button" onClick={() => onClick?.(id)} className={cn(DASHBOARD_DOCUMENT_ROW_GRID, 'w-full text-left')}>
      {/* 문서 열 — 이 행에서 폭을 흡수하는 유일한 슬롯 */}
      <span className="flex min-w-0 items-center gap-4">
        <span
          className={cn(
            'flex shrink-0 rounded-lg p-2',
            hasConflictIcon
              ? 'bg-accent-red-lighten text-accent-red-default'
              : 'bg-fill-normal-strong text-icon-normal-alternative',
          )}
        >
          <LeadingIcon aria-hidden className="size-6" />
        </span>

        {/* 제목 23 + gap 2 + breadcrumbs 28 = 53. 행 높이 65는 여기서 파생되므로 h-*를 두지 않는다 */}
        <span className="flex min-w-0 flex-col justify-center gap-0.5">
          <span className="text-heading-small text-text-normal-normal truncate">{title}</span>

          {breadcrumbs.length > 0 && (
            <span className="flex min-w-0 items-center">
              {breadcrumbs.map((crumb, index) => {
                const CrumbIcon = BREADCRUMB_ICON[crumb.kind];

                return (
                  <Fragment key={`${crumb.kind}-${crumb.label}`}>
                    {index > 0 && <IconArrowRight aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}
                    {/* Text Button(408:1916) — padding 4/6, gap 4, radius 1000 */}
                    <span className="flex min-w-0 items-center gap-1 rounded-full px-1.5 py-1">
                      {CrumbIcon && <CrumbIcon aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}
                      <span className="text-body-xsmall text-text-normal-neutral truncate">{crumb.label}</span>
                    </span>
                  </Fragment>
                );
              })}
            </span>
          )}
        </span>
      </span>

      {/* 상태 열 */}
      <span className="flex items-center">
        <DocumentStatusBadge status={status} />
      </span>

      {/* 태그 열 — 칩 슬롯이 1개뿐이라(142 + gap 8 + 34 = 184) 나머지는 "+N"으로 접는다 */}
      <span className="flex items-center gap-2">
        {visibleTag && (
          <span className="text-body-small bg-accent-light-blue-lighten text-accent-light-blue-default min-w-0 flex-1 truncate rounded-lg px-2 py-1">
            {visibleTag}
          </span>
        )}
        {collapsedTags.length > 0 && (
          <span className="text-body-small bg-fill-normal-strong text-accent-light-blue-default shrink-0 rounded-lg px-2 py-1">
            +{collapsedTags.length}
          </span>
        )}
      </span>

      {/* 최근 활동 열 — Figma textAlign RIGHT */}
      <span className="text-body-small text-text-normal-alternative text-right">{lastActivityLabel}</span>
    </button>
  );
}
