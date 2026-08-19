import IconFolderFilled from '@/public/icons/icon/folder_filled.svg';

import type { DocumentBreadcrumb, WikiChannel, WikiFolder } from '../../types/llmWikiModel';
import { DashboardDocumentTableHeader } from '../document/DashboardDocumentRow';
import FolderDocumentRow, { type FolderDocumentRowItem } from '../document/FolderDocumentRow';
import DocumentTableEmptyState from '../document/states/DocumentTableEmptyState';
import WikiPageHeader from '../header/WikiPageHeader';
import WikiSpaceTableFooter from './WikiSpaceTableFooter';
import WikiSpaceTitleBlock from './WikiSpaceTitleBlock';

interface WikiFolderPageProps {
  channel: WikiChannel;
  folder: WikiFolder;
  /** 문서 행 표시 데이터 — 담당자·상태 표시 필드는 목록 API 미동봉분이다 */
  documentRows: readonly FolderDocumentRowItem[];
  authorName?: string;
  authorProfileImageUrl?: string | null;
  pageSize: number;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPageSizeClick?: () => void;
  onDocumentClick?: (documentId: string) => void;
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
}

/** 폴더 메인 페이지 — breadcrumb는 채널>폴더 2마디로 끝난다(폴더 depth 1 계약). */
export default function WikiFolderPage({
  channel,
  folder,
  documentRows,
  authorName,
  authorProfileImageUrl,
  pageSize,
  currentPage,
  totalPages,
  onPageChange,
  onPageSizeClick,
  onDocumentClick,
  onBreadcrumbClick,
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
      />

      {/* 상단 커버 — 바탕만 시안값이고 콘텐츠는 미정이라 비워 둔다 */}
      <div aria-hidden className="bg-fill-normal-strong h-50 shrink-0" />

      <div className="flex flex-col gap-9 px-20 py-9">
        <WikiSpaceTitleBlock
          icon={<IconFolderFilled />}
          name={folder.name}
          authorName={authorName}
          authorProfileImageUrl={authorProfileImageUrl}
        />

        <div className="flex flex-col gap-8">
          <div className="flex flex-col">
            <DashboardDocumentTableHeader />
            {documentRows.length === 0 ? (
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
            onPageSizeClick={onPageSizeClick}
          />
        </div>
      </div>
    </div>
  );
}
