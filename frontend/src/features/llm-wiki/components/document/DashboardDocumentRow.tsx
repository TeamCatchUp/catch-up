import { Fragment } from 'react';

import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';
import IconFileFilled from '@/public/icons/icon/file_filled.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { DocumentBreadcrumb, DocumentRowData } from '../../types/llmWikiModel';
import { BREADCRUMB_ICON } from '../breadcrumbIcons';
import DocumentStatusBadge from './DocumentStatusBadge';

/**
 * 행·헤더가 공유하는 표 레이아웃. 문서 열 하나만 폭을 흡수하고(min-w 220),
 * 메타 열 3개(140/160/96)는 행끼리·헤더와 열을 맞추기 위한 고정폭이다.
 */
export const DASHBOARD_DOCUMENT_TABLE_SHELL = 'flex items-center gap-9 p-1.5';
export const DASHBOARD_DOCUMENT_META_GRID = 'grid shrink-0 grid-cols-[140px_160px_96px] items-center gap-4';

/** 표 머리글. 행과 같은 레이아웃 상수를 써서 열이 어긋나지 않게 한다. */
export function DashboardDocumentTableHeader() {
  return (
    <div className={cn(DASHBOARD_DOCUMENT_TABLE_SHELL, 'text-body-small text-text-normal-alternative')}>
      <span className="min-w-55 flex-1 truncate">문서</span>
      <span className={DASHBOARD_DOCUMENT_META_GRID}>
        <span className="truncate">담당자</span>
        <span className="truncate">상태</span>
        <span className="truncate text-right">최근 활동</span>
      </span>
    </div>
  );
}

interface DashboardDocumentRowProps {
  document: DocumentRowData;
  onClick?: (id: string) => void;
  onBreadcrumbClick?: (breadcrumb: DocumentBreadcrumb) => void;
}

export default function DashboardDocumentRow({ document, onClick, onBreadcrumbClick }: DashboardDocumentRowProps) {
  const { id, title, breadcrumbs, status, owners, lastActivityLabel } = document;
  const [owner] = owners;

  // hover 채움은 시안에 없고 DS 중립 상호작용 토큰을 채택한 것이다(사용자 확정).
  return (
    <div
      className={cn(
        DASHBOARD_DOCUMENT_TABLE_SHELL,
        'hover:bg-fill-normal-interaction-hover relative w-full rounded-lg transition-colors',
      )}
    >
      {/* 행 전체 클릭 — 마디 버튼과의 중첩을 피해 오버레이로 분리한다 */}
      <button
        type="button"
        aria-label={title}
        onClick={() => onClick?.(id)}
        className="absolute inset-0 rounded-lg"
      />

      {/* 문서 열 — 이 행에서 폭을 흡수하는 유일한 슬롯 */}
      <span className="flex min-w-55 flex-1 items-center gap-4">
        <span className="bg-fill-normal-strong text-icon-normal-alternative flex shrink-0 rounded-lg p-2">
          <IconFileFilled aria-hidden className="size-6" />
        </span>

        {/* 행 높이는 내용물에서 파생되므로 h-*를 두지 않는다 */}
        <span className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
          <span className="text-heading-small text-text-normal-normal truncate">{title}</span>

          {breadcrumbs.length > 0 && (
            <span className="flex min-w-0 items-center">
              {breadcrumbs.map((crumb, index) => {
                const CrumbIcon = BREADCRUMB_ICON[crumb.kind];

                return (
                  <Fragment key={`${crumb.kind}-${crumb.label}`}>
                    {index > 0 && <IconArrowRight aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}
                    {/* breadcrumb 마디 — 공용 Text Button, 시안이 마디 폭을 150으로 상한 */}
                    <Button
                      variant="text-secondary-mono"
                      size="sm"
                      onClick={() => onBreadcrumbClick?.(crumb)}
                      className="relative max-w-37.5 min-w-0 shrink"
                    >
                      {CrumbIcon && <CrumbIcon aria-hidden className="text-icon-normal-neutral size-5 shrink-0" />}
                      <span className="text-body-xsmall text-text-normal-neutral min-w-0 flex-1 truncate">
                        {crumb.label}
                      </span>
                    </Button>
                  </Fragment>
                );
              })}
            </span>
          )}
        </span>
      </span>

      <span className={DASHBOARD_DOCUMENT_META_GRID}>
        {/* 담당자 열 — 이름이 바로 옆이라 아바타 alt는 비운다(중복 낭독 방지).
            미지정(빈 배열)과 2인 이상 표기는 시안이 없어 첫 담당자만 렌더한다 */}
        <span className="flex min-w-0 items-center gap-3">
          {owner && (
            <>
              <Avatar
                size="small"
                src={owner.profileImageUrl}
                className="border-line-normal-assistive shrink-0 rounded-xl"
              />
              <span className="text-body-small text-text-normal-normal truncate">{owner.displayName}</span>
            </>
          )}
        </span>

        {/* 상태 열 */}
        <span className="flex min-w-0 items-center">
          <DocumentStatusBadge status={status} />
        </span>

        {/* 최근 활동 열 — 우측 정렬 */}
        <span className="text-body-small text-text-normal-alternative truncate text-right">{lastActivityLabel}</span>
      </span>
    </div>
  );
}
