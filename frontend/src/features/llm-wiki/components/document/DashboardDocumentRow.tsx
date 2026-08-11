import { Fragment } from 'react';

import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconErrorFilled from '@/public/icons/icon/error_filled.svg';
import IconFileFilled from '@/public/icons/icon/file_filled.svg';
import { cn } from '@/shared/utils/cn';

import type { DocumentRowData } from '../../types/llmWikiModel';
import { BREADCRUMB_ICON } from '../breadcrumbIcons';
import DocumentStatusBadge from './DocumentStatusBadge';

/**
 * 대시보드 문서 표의 열 템플릿. 고정폭 3개는 행끼리·헤더와 열을 맞추기 위한 것이다.
 * 표 헤더가 생기면 이 상수를 함께 쓴다.
 */
export const DASHBOARD_DOCUMENT_ROW_GRID =
  'grid grid-cols-[minmax(0,1fr)_194px_184px_96px] items-center gap-4 rounded-lg p-1.5';

interface DashboardDocumentRowProps {
  document: DocumentRowData;
  onClick?: (id: string) => void;
}

export default function DashboardDocumentRow({ document, onClick }: DashboardDocumentRowProps) {
  const { id, title, breadcrumbs, status, hasConflictIcon, tags, lastActivityLabel } = document;
  const [visibleTag, ...collapsedTags] = tags;

  // 충돌 행은 선두 아이콘만 갈린다.
  const LeadingIcon = hasConflictIcon ? IconErrorFilled : IconFileFilled;

  // hover 채움은 시안에 정의가 없어 발명하지 않는다.
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

        {/* 행 높이는 내용물에서 파생되므로 h-*를 두지 않는다 */}
        <span className="flex min-w-0 flex-col justify-center gap-0.5">
          <span className="text-heading-small text-text-normal-normal truncate">{title}</span>

          {breadcrumbs.length > 0 && (
            <span className="flex min-w-0 items-center">
              {breadcrumbs.map((crumb, index) => {
                const CrumbIcon = BREADCRUMB_ICON[crumb.kind];

                return (
                  <Fragment key={`${crumb.kind}-${crumb.label}`}>
                    {index > 0 && <IconArrowRight aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}
                    {/* breadcrumb 마디 */}
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

      {/* 태그 열 — 칩 슬롯이 1개뿐이라 나머지는 "+N"으로 접는다 */}
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

      {/* 최근 활동 열 — 우측 정렬 */}
      <span className="text-body-small text-text-normal-alternative text-right">{lastActivityLabel}</span>
    </button>
  );
}
