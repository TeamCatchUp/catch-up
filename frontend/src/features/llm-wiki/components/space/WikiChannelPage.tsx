import IconWikiChannelFilled from '@/public/icons/icon/wiki_channel_filled.svg';

import type { WikiChannelListItem } from '../../types/llmWikiModel';
import { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import FolderDocumentRow, { type FolderDocumentRowItem } from '../document/FolderDocumentRow';
import DocumentTableEmptyState from '../document/states/DocumentTableEmptyState';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from './WikiSpaceTableFooter';
import WikiSpaceTitleBlock from './WikiSpaceTitleBlock';

interface WikiChannelPageProps {
  channel: WikiChannelListItem;
  /** 폴더 행 표시 데이터 — channel.folders와 1:1. 담당자·상태 표시 필드는 목록 API 미동봉분이다 */
  folderRows: readonly FolderDocumentRowItem[];
  authorName?: string;
  authorProfileImageUrl?: string | null;
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** 쪽 크기 선택. 주면 푸터 표시가 드롭다운으로 열린다 */
  onPageSizeChange?: (pageSize: number) => void;
  onFolderClick?: (folderId: string) => void;
}

/** 채널 메인 페이지 — breadcrumb 헤더(채널 1마디) + 이름 블록 + 폴더 목록 표. */
export default function WikiChannelPage({
  channel,
  folderRows,
  authorName,
  authorProfileImageUrl,
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onPageSizeChange,
  onFolderClick,
}: WikiChannelPageProps) {
  return (
    <div className="flex flex-col">
      <WikiPageHeader variant="detail" breadcrumbs={[{ kind: 'channel', label: channel.name }]} />

      {/* 상단 커버 — 바탕만 시안값이고 콘텐츠는 미정이라 비워 둔다 */}
      <div aria-hidden className="bg-fill-normal-strong h-50 shrink-0" />

      <div className="flex flex-col gap-9 px-20 py-9">
        <WikiSpaceTitleBlock
          icon={<IconWikiChannelFilled />}
          name={channel.name}
          authorName={authorName}
          authorProfileImageUrl={authorProfileImageUrl}
        />

        <div className="flex flex-col gap-8">
          <div className="flex flex-col">
            <DashboardDocumentTableHeader />
            {folderRows.length === 0 ? (
              <DocumentTableEmptyState message="폴더가 없어요" />
            ) : (
              <div className="flex flex-col gap-1">
                {folderRows.map((row) => (
                  <FolderDocumentRow key={row.id} kind="folder" item={row} onClick={onFolderClick} />
                ))}
              </div>
            )}
          </div>

          <WikiSpaceTableFooter
            pageSize={pageSize}
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
          />
        </div>
      </div>
    </div>
  );
}
