import IconFileFilled from '@/public/icons/icon/file_filled.svg';
import IconFolderFilled from '@/public/icons/icon/folder_filled.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/shared/utils/cn';

import type { DocumentStatus } from '../../types/llmWikiModel';
import { DASHBOARD_DOCUMENT_META_GRID, DASHBOARD_DOCUMENT_TABLE_SHELL } from './DashboardDocumentRow';
import DocumentStatusBadge from './DocumentStatusBadge';

/** 채널 페이지의 폴더 행과 폴더 페이지의 문서 행 — 아이콘만 갈리고 열 구성은 같다 */
export type FolderDocumentRowKind = 'folder' | 'document';

export interface FolderDocumentRowItem {
  id: string;
  name: string;
  /** 담당자 표시명·이미지 — 목록 API에 대응 필드가 없다(협상 대상, 감사 8/13 부록) */
  ownerName: string;
  ownerProfileImageUrl: string | null;
  status: DocumentStatus;
  lastActivityLabel: string;
}

interface FolderDocumentRowProps {
  kind: FolderDocumentRowKind;
  item: FolderDocumentRowItem;
  onClick?: (id: string) => void;
}

const ROW_ICON: Record<FolderDocumentRowKind, typeof IconFolderFilled> = {
  folder: IconFolderFilled,
  document: IconFileFilled,
};

/**
 * 채널·폴더 페이지 목록의 한 행. 열 기하는 대시보드 표와 동일해서
 * DashboardDocumentRow의 셸·그리드 상수를 그대로 공유한다.
 */
export default function FolderDocumentRow({ kind, item, onClick }: FolderDocumentRowProps) {
  const { id, name, ownerName, ownerProfileImageUrl, status, lastActivityLabel } = item;
  const RowIcon = ROW_ICON[kind];

  // hover 채움은 시안에 정의가 없어 발명하지 않는다.
  return (
    <button
      type="button"
      onClick={() => onClick?.(id)}
      className={cn(DASHBOARD_DOCUMENT_TABLE_SHELL, 'w-full rounded-lg text-left')}
    >
      {/* 이름 열 — 이 행에서 폭을 흡수하는 유일한 슬롯. 경로 줄이 없는 1줄 행이다 */}
      <span className="flex min-w-55 flex-1 items-center gap-4">
        <span className="bg-fill-normal-strong text-icon-normal-alternative flex shrink-0 rounded-lg p-2">
          <RowIcon aria-hidden className="size-6" />
        </span>
        <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{name}</span>
      </span>

      <span className={DASHBOARD_DOCUMENT_META_GRID}>
        {/* 담당자 열 — 이름이 바로 옆이라 아바타 alt는 비운다(중복 낭독 방지) */}
        <span className="flex min-w-0 items-center gap-3">
          <Avatar size="small" src={ownerProfileImageUrl} className="border-line-normal-assistive shrink-0 rounded-xl" />
          <span className="text-body-small text-text-normal-normal truncate">{ownerName}</span>
        </span>

        {/* 상태 열 */}
        <span className="flex min-w-0 items-center">
          <DocumentStatusBadge status={status} />
        </span>

        {/* 최근 활동 열 — 우측 정렬 */}
        <span className="text-body-small text-text-normal-alternative truncate text-right">{lastActivityLabel}</span>
      </span>
    </button>
  );
}
