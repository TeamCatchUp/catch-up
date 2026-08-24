import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import IconWikiChannelFilled from '@/public/icons/icon/wiki_channel_filled.svg';

import type { WikiChannelListItem } from '../../types/llmWikiModel';
import FolderDocumentRow, {
  type FolderDocumentRowItem,
  FolderDocumentTableHeader,
} from '../document/FolderDocumentRow';
import DocumentTableEmptyState from '../document/states/DocumentTableEmptyState';
import WikiHeaderActions from '../header/WikiHeaderActions';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from './WikiSpaceTableFooter';
import WikiSpaceTitleBlock from './WikiSpaceTitleBlock';

interface WikiChannelPageProps {
  channel: WikiChannelListItem;
  /** 폴더 행 표시 데이터 — channel.folders와 1:1. 폴더에는 담당자·상태에 대응하는 필드가 없다 */
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
  onCopyLink?: () => void;
  /** 채널 관리자만 넘어온다 — 없으면 헤더 케밥이 서지 않는다 */
  onRenameSubmit?: (name: string) => void;
}

/** 채널 메인 페이지 — 아이콘+제목 헤더 + 이름 블록 + 폴더 목록 표. */
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
  onCopyLink,
  onRenameSubmit,
}: WikiChannelPageProps) {
  return (
    <div className="flex flex-col">
      <WikiPageHeader
        variant="main"
        icon={<IconWikiChannel />}
        title={channel.name}
        actions={
          onCopyLink && (
            <WikiHeaderActions
              variant="main"
              kind="channel"
              name={channel.name}
              onCopyLink={onCopyLink}
              onRenameSubmit={onRenameSubmit}
            />
          )
        }
      />

      <div className="flex flex-col gap-9 px-20 py-9">
        <WikiSpaceTitleBlock
          icon={<IconWikiChannelFilled />}
          name={channel.name}
          authorName={authorName}
          authorProfileImageUrl={authorProfileImageUrl}
        />

        <div className="flex flex-col gap-8">
          <div className="flex flex-col">
            <FolderDocumentTableHeader kind="folder" />
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
