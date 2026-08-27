import IconInfoFilled from '@/public/icons/icon/info_filled.svg';

import type { DocumentBreadcrumb } from '../../../types/llmWikiModel';
import type { DocumentOwner } from '../../../types/llmWikiModel';
import DocumentPresentation from '../../document/DocumentPresentation';
import WikiDocumentShell from '../../document/WikiDocumentShell';
import type { ProposalPreviewItem } from './composeProposalPreview';

export const PREVIEW_GUIDE =
  '검토 중인 제안본을 미리 보고 있습니다. 판정 결과가 반영된 모습이며, 최종 내보내기 전에는 실제 문서가 바뀌지 않습니다.';

export interface ProposalPreviewPageProps {
  title: string;
  owners: readonly DocumentOwner[];
  timeLabel: string;
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
  owners,
  timeLabel,
  breadcrumbs,
  items,
  onBreadcrumbClick,
}: ProposalPreviewPageProps) {
  return (
    <WikiDocumentShell
      title={title}
      owners={owners}
      timeLabel={timeLabel}
      topContent={
        <div className="bg-fill-normal-strong flex items-start gap-1.5 rounded-lg px-2 py-1.5 break-keep">
          <IconInfoFilled aria-hidden className="text-icon-normal-normal size-4.5 shrink-0" />
          <span className="text-body-xsmall text-text-normal-neutral">{PREVIEW_GUIDE}</span>
        </div>
      }
      breadcrumbs={breadcrumbs}
      onBreadcrumbClick={onBreadcrumbClick}
    >
      <DocumentPresentation items={items} />
    </WikiDocumentShell>
  );
}
