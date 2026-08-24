import IconFolderFilled from '@/public/icons/icon/folder_filled.svg';

import type { DocumentBreadcrumb, WikiChannel, WikiFolder } from '../../types/llmWikiModel';
import FolderDocumentRow, {
  type FolderDocumentRowItem,
  FolderDocumentTableHeader,
} from '../document/FolderDocumentRow';
import DocumentTableEmptyState from '../document/states/DocumentTableEmptyState';
import DocumentTableSkeleton from '../document/states/DocumentTableSkeleton';
import WikiHeaderActions from '../header/WikiHeaderActions';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from './WikiSpaceTableFooter';
import WikiSpaceTitleBlock from './WikiSpaceTitleBlock';

interface WikiFolderPageProps {
  channel: WikiChannel;
  folder: WikiFolder;
  /** 문서 행 표시 데이터 — 담당자·상태·최근 활동 모두 문서 목록 응답에서 온다 */
  documentRows: readonly FolderDocumentRowItem[];
  /** 첫 조회가 끝나기 전인지. 쪽 이동은 이전 쪽을 그대로 두므로 여기 해당하지 않는다 */
  documentsLoading?: boolean;
  authorName?: string;
  authorProfileImageUrl?: string | null;
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** 쪽 크기 선택. 주면 푸터 표시가 드롭다운으로 열린다 */
  onPageSizeChange?: (pageSize: number) => void;
  onDocumentClick?: (documentId: string) => void;
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
  onCopyLink?: () => void;
  /** 채널 관리자만 넘어온다 — 없으면 헤더 케밥이 서지 않는다 */
  onRenameSubmit?: (name: string) => void;
}

/** 폴더 메인 페이지 — breadcrumb는 채널>폴더 2마디로 끝난다(폴더 depth 1 계약). */
export default function WikiFolderPage({
  channel,
  folder,
  documentRows,
  documentsLoading = false,
  authorName,
  authorProfileImageUrl,
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onPageSizeChange,
  onDocumentClick,
  onBreadcrumbClick,
  onCopyLink,
  onRenameSubmit,
}: WikiFolderPageProps) {
  return (
    <div className="flex flex-col">
      <WikiPageHeader
        variant="detail"
        breadcrumbs={[
          { kind: 'channel', label: channel.name },
          { kind: 'folder', label: folder.name },
        ]}
        onBreadcrumbClick={onBreadcrumbClick}
        actions={
          onCopyLink && (
            <WikiHeaderActions
              variant="detail"
              kind="folder"
              name={folder.name}
              onCopyLink={onCopyLink}
              onRenameSubmit={onRenameSubmit}
            />
          )
        }
      />

      <div className="flex flex-col gap-9 px-20 py-9">
        <WikiSpaceTitleBlock
          icon={<IconFolderFilled />}
          name={folder.name}
          authorName={authorName}
          authorProfileImageUrl={authorProfileImageUrl}
        />

        <div className="flex flex-col gap-8">
          <div className="flex flex-col">
            <FolderDocumentTableHeader kind="document" />
            {documentsLoading ? (
              <DocumentTableSkeleton />
            ) : documentRows.length === 0 ? (
              <DocumentTableEmptyState />
            ) : (
              <div className="flex flex-col gap-1">
                {documentRows.map((row) => (
                  <FolderDocumentRow key={row.id} kind="document" item={row} onClick={onDocumentClick} />
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
