import { Button } from '@/shared/components/ui/button';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import BlockDiffCard from './BlockDiffCard';

export interface BlockDiffSectionProps {
  entries: readonly BlockDiffEntry[];
  /** 헤더 우상단 "직접 수정" — 눌렀을 때의 동작(본 페이지 이동 등)은 미정이라 콜백만 뚫어 둔다 */
  onEditDocument: () => void;
  onApprove: (id: string) => void;
  onRevert: (id: string) => void;
  onDelete: (id: string) => void;
  /** 카드의 연필 버튼 — 블록 단위 편집. 진입 후 UI는 디자인 미정 */
  onEditRequest: (id: string) => void;
}

/**
 * 검토 큐 상세의 "수정 내용" 영역(Figma 17564:127037).
 *
 * 변경 0건의 빈 상태 시각은 시안에 없어(MISSING) 발명하지 않는다 —
 * 건수 배지 0으로 헤더만 남는 것이 현재 계약이고, design-request로 확인 요청 상태다.
 */
export default function BlockDiffSection({
  entries,
  onEditDocument,
  onApprove,
  onRevert,
  onDelete,
  onEditRequest,
}: BlockDiffSectionProps) {
  return (
    <section className="flex w-full flex-col gap-3">
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <h2 className="text-heading-medium text-text-normal-normal">수정 내용</h2>
            <span className="bg-fill-normal-strong text-body-small text-text-normal-neutral rounded-md px-2 py-0.5">
              {entries.length}
            </span>
          </div>
          <p className="text-body-small text-text-normal-assistive">작성자가 변경한 내용입니다.</p>
        </div>
        <Button variant="box-outline-gray" size="md" onClick={onEditDocument}>
          직접 수정
        </Button>
      </header>

      {entries.map((entry) => (
        <BlockDiffCard
          key={entry.id}
          entry={entry}
          onApprove={onApprove}
          onRevert={onRevert}
          onDelete={onDelete}
          onEditRequest={onEditRequest}
        />
      ))}
    </section>
  );
}
