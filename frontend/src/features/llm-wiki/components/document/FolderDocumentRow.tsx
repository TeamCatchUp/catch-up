import IconFileFilled from '@/public/icons/icon/file_filled.svg';
import IconFolderFilled from '@/public/icons/icon/folder_filled.svg';
import { Avatar } from '@/shared/components/ui/avatar';
import { cn } from '@/shared/utils/cn';

import type { DocumentOwner, DocumentStatus } from '../../types/llmWikiModel';
import { DASHBOARD_DOCUMENT_META_GRID, DASHBOARD_DOCUMENT_TABLE_SHELL } from './DashboardDocumentRow';
import DocumentStatusBadge from './DocumentStatusBadge';

/** 채널 페이지의 폴더 행과 폴더 페이지의 문서 행 — 아이콘과 메타 열 구성이 갈린다 */
export type FolderDocumentRowKind = 'folder' | 'document';

export interface FolderDocumentRowItem {
  id: string;
  name: string;
  /** 문서 행에만 있다. 빈 배열은 미지정이고, 2인 이상은 세로로 쌓인다 */
  owners?: readonly DocumentOwner[];
  /** 문서 행에만 있다 */
  status?: DocumentStatus;
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

/** 폴더에는 담당자·상태에 대응하는 필드가 없다 — 빈 열을 두지 않고 최근 활동만 남긴다 */
export const FOLDER_DOCUMENT_META_GRID: Record<FolderDocumentRowKind, string> = {
  folder: 'grid shrink-0 grid-cols-[96px] items-center gap-4',
  document: DASHBOARD_DOCUMENT_META_GRID,
};

/** 채널·폴더 페이지 표 머리글. 행과 같은 상수를 써서 열이 어긋나지 않게 한다 */
export function FolderDocumentTableHeader({ kind }: { kind: FolderDocumentRowKind }) {
  return (
    <div className={cn(DASHBOARD_DOCUMENT_TABLE_SHELL, 'text-body-small text-text-normal-alternative')}>
      <span className="min-w-55 flex-1 truncate">문서</span>
      <span className={FOLDER_DOCUMENT_META_GRID[kind]}>
        {kind === 'document' && (
          <>
            <span className="truncate">담당자</span>
            <span className="truncate">상태</span>
          </>
        )}
        <span className="truncate text-center">최근 활동</span>
      </span>
    </div>
  );
}

/**
 * 채널·폴더 페이지 목록의 한 행. 셸과 문서 행의 열 기하는 대시보드 표 상수를 공유하고,
 * 폴더 행만 담당자·상태 열을 두지 않는다.
 */
export default function FolderDocumentRow({ kind, item, onClick }: FolderDocumentRowProps) {
  const { id, name, owners, status, lastActivityLabel } = item;
  const RowIcon = ROW_ICON[kind];

  // hover 채움은 시안에 없고 대시보드 행과 같은 DS 중립 상호작용 토큰을 따른다.
  // 갈 곳이 없는 행에는 걸지 않는다 — 눌리지 않는데 눌릴 것처럼 보인다.
  return (
    <button
      type="button"
      onClick={() => onClick?.(id)}
      className={cn(
        DASHBOARD_DOCUMENT_TABLE_SHELL,
        'w-full rounded-lg text-left transition-colors',
        onClick && 'hover:bg-fill-normal-interaction-hover cursor-pointer',
      )}
    >
      {/* 이름 열 — 이 행에서 폭을 흡수하는 유일한 슬롯. 경로 줄이 없는 1줄 행이다 */}
      <span className="flex min-w-55 flex-1 items-center gap-4">
        <span className="bg-fill-normal-strong text-icon-normal-alternative flex shrink-0 rounded-lg p-2">
          <RowIcon aria-hidden className="size-6" />
        </span>
        <span className="text-heading-small text-text-normal-normal min-w-0 flex-1 truncate">{name}</span>
      </span>

      <span className={FOLDER_DOCUMENT_META_GRID[kind]}>
        {kind === 'document' && (
          <>
            {/* 담당자 열 — 이름이 바로 옆이라 아바타 alt는 비운다(중복 낭독 방지).
                전원을 세로로 쌓아 행 높이가 인원수만큼 늘어난다. 미지정(빈 배열)은 기본 아바타+문구 */}
            <span className="flex min-w-0 flex-col gap-1">
              {!owners?.length && (
                <span className="flex min-w-0 items-center gap-3">
                  <Avatar size="small" className="border-line-normal-assistive shrink-0 rounded-xl" />
                  <span className="text-body-small text-text-normal-assistive truncate">담당자 없음</span>
                </span>
              )}
              {owners?.map((owner) => (
                <span key={owner.userId} className="flex min-w-0 items-center gap-3">
                  <Avatar
                    size="small"
                    src={owner.profileImageUrl}
                    className="border-line-normal-assistive shrink-0 rounded-xl"
                  />
                  <span className="text-body-small text-text-normal-normal truncate">{owner.displayName}</span>
                </span>
              ))}
            </span>

            {/* 상태 열 */}
            <span className="flex min-w-0 items-center">
              {status !== undefined && <DocumentStatusBadge status={status} />}
            </span>
          </>
        )}

        {/* 최근 활동 열 */}
        <span className="text-body-small text-text-normal-alternative truncate text-center">{lastActivityLabel}</span>
      </span>
    </button>
  );
}
