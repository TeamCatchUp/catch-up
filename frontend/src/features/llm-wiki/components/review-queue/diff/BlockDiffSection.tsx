import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import BlockDiffCard from './BlockDiffCard';

export interface BlockDiffSectionProps {
  entries: readonly BlockDiffEntry[];
  /** [BE] can_review. 카드의 판정 버튼과 헤더의 전체 승인·반려 노출을 정한다 */
  canReview?: boolean;
  /** 카드별 반려 진입점. 사유 입력 자리가 없으면 꺼서 보낼 수 없는 요청을 막는다 */
  canReject?: boolean;
  onApprove: (id: string) => void;
  /** 제안 기각 */
  onReject: (id: string) => void;
  onReset?: (id: string) => void;
  resetPending?: boolean;
}

/**
 * 검토 큐 상세의 "변경 내용" 영역.
 * 변경 0건의 빈 상태 시각은 시안에 없어 발명하지 않는다 — 건수 배지 0으로 헤더만 남는다.
 */
export default function BlockDiffSection({
  entries,
  canReview = true,
  canReject = true,
  onApprove,
  onReject,
  onReset,
  resetPending = false,
}: BlockDiffSectionProps) {
  return (
    <section className="flex w-full flex-col gap-3">
      <header className="flex items-start gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex items-center gap-3">
            <h2 className="text-heading-medium text-text-normal-normal">변경 내용</h2>
            <span className="bg-fill-normal-strong text-body-small text-text-normal-neutral rounded-md px-2 py-0.5">
              {entries.length}
            </span>
          </div>
          <p className="text-body-small text-text-normal-assistive">작성자가 변경한 내용입니다.</p>
        </div>
      </header>

      {/* 판정이 끝난 카드는 접은 채로 남는다 — 결정한 블록을 다시 훑을 이유가 없다 */}
      {entries.map((entry) => (
        <BlockDiffCard
          key={entry.id}
          entry={entry}
          defaultCollapsed={Boolean(entry.approved || entry.rejected)}
          // 판정 경로가 없는 카드(빠진 블록)는 열람만 남긴다 — 닿는 곳 없는 버튼을 두지 않는다
          canReview={canReview && entry.blockIndex !== null}
          canReject={canReject}
          onApprove={onApprove}
          onReject={onReject}
          onReset={onReset}
          resetPending={resetPending}
        />
      ))}
    </section>
  );
}
