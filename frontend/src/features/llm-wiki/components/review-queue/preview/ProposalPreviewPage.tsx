import IconInfoFilled from '@/public/icons/icon/info_filled.svg';

import type { DocumentBreadcrumb } from '../../../types/llmWikiModel';
import WikiDocumentShell, { DocumentSection, DocumentTable } from '../../document/WikiDocumentShell';
import type { ProposalPreviewItem } from './composeProposalPreview';

/** 발행 시각 자리를 대신하는 표기 — 아직 발행되지 않은 판이라는 사실을 알린다 */
export const PREVIEW_NOTICE = '검토 중인 제안본 미리보기';

/** 본문 위 안내 — 판정 반영본이고 내보내기 전에는 문서가 바뀌지 않는다는 계약을 알린다 */
export const PREVIEW_GUIDE =
  '검토 중인 제안본을 미리 보고 있습니다. 판정 결과가 반영된 모습이며, 최종 내보내기 전에는 실제 문서가 바뀌지 않습니다.';

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
      {/* 담당자 카드의 안내 배너 패턴을 그대로 쓴다 */}
      <div className="bg-fill-normal-strong flex items-center gap-2 rounded-lg px-2 py-1.5">
        <IconInfoFilled aria-hidden className="text-icon-normal-neutral size-4.5 shrink-0" />
        <span className="text-body-xsmall text-text-normal-neutral min-w-0">{PREVIEW_GUIDE}</span>
      </div>
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
