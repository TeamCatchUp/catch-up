import IconOpenInNew from '@/public/icons/icon/open_in_new_24.svg';
import { Button } from '@/shared/components/ui/button';

import type { BlockDiffEntry } from '../../../types/llmWikiDiff';
import BlockDiffCard from './BlockDiffCard';

export interface BlockDiffSectionProps {
  entries: readonly BlockDiffEntry[];
  /** 헤더 우상단 "미리보기". 동작이 미정이라 콜백만 뚫어 둔다 */
  onPreview: () => void;
  onApprove: (id: string) => void;
  /** 제안 기각 */
  onReject: (id: string) => void;
}

/**
 * 검토 큐 상세의 "수정 내용" 영역.
 * 변경 0건의 빈 상태 시각은 시안에 없어 발명하지 않는다 — 건수 배지 0으로 헤더만 남는다.
 */
export default function BlockDiffSection({
  entries,
  onPreview,
  onApprove,
  onReject,
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
        <Button variant="box-outline-gray" size="md" onClick={onPreview}>
          미리보기
          <IconOpenInNew aria-hidden className="size-5" />
        </Button>
      </header>

      {entries.map((entry) => (
        <BlockDiffCard
          key={entry.id}
          entry={entry}
          onApprove={onApprove}
          onReject={onReject}
        />
      ))}
    </section>
  );
}
