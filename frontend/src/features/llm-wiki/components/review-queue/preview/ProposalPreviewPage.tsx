import type { DocumentBreadcrumb } from '../../../types/llmWikiModel';
import WikiDocumentShell, { DocumentSection, DocumentTable } from '../../document/WikiDocumentShell';
import type { ProposalPreviewItem } from './composeProposalPreview';

/** 발행 시각 자리를 대신하는 표기 — 아직 발행되지 않은 판이라는 사실을 알린다 */
export const PREVIEW_NOTICE = '검토 중인 제안본 미리보기';

export interface ProposalPreviewPageProps {
  title: string;
  /** 채널 > 폴더 > 문서. 이름 join 결과라 상세 응답이 아니라 밖에서 받는다 */
  breadcrumbs: readonly DocumentBreadcrumb[];
  items: readonly ProposalPreviewItem[];
  onBreadcrumbClick?: (crumb: DocumentBreadcrumb, index: number) => void;
}

/**
 * 검토 중인 변경안을 판정 반영본으로 읽는 화면. 문서 열람과 같은 셸·부품을 쓴다.
 * 발행판이 아니라 편집·판정 경로를 두지 않고, 발행 시각 자리에는 미리보기 표기가 선다.
 */
export default function ProposalPreviewPage({
  title,
  breadcrumbs,
  items,
  onBreadcrumbClick,
}: ProposalPreviewPageProps) {
  return (
    <WikiDocumentShell
      title={title}
      caption={PREVIEW_NOTICE}
      breadcrumbs={breadcrumbs}
      onBreadcrumbClick={onBreadcrumbClick}
    >
      {items.map((item, position) =>
        item.kind === 'table' ? (
          <DocumentTable key={`table-${position}`} heading={item.heading} rows={item.rows} />
        ) : (
          <DocumentSection key={`section-${position}`} heading={item.heading} text={item.text} />
        ),
      )}
    </WikiDocumentShell>
  );
}
