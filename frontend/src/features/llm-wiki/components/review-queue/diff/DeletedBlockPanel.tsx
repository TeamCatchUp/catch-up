import IconBackspace from '@/public/icons/icon/backspace.svg';

import type { DiffLine } from '../../../types/llmWikiDiff';

interface DeletedBlockPanelProps {
  lines: readonly DiffLine[];
}

/**
 * 블록이 통째로 지워지는 제안의 본문. 대조할 상대가 없어 줄 단위 호버가 없다.
 * "콘텐츠를 삭제함" 고지는 색만으로 삭제를 알리지 않기 위한 것이라 지우면 안 된다.
 */
export default function DeletedBlockPanel({ lines }: DeletedBlockPanelProps) {
  return (
    <div className="bg-surface-red-subtle border-accent-red-default flex flex-col gap-2 border-l-2 px-3 py-2">
      <p className="text-body-xsmall text-status-destructive flex items-center gap-1.5">
        <IconBackspace aria-hidden className="size-5" />
        콘텐츠를 삭제함
      </p>
      <div className="text-reading-body-md-small text-text-normal-normal">
        {lines.map((line, lineIndex) => (
          <p key={lineIndex} className="min-h-6.5">
            {line.segments.map((segment) => segment.text).join('')}
          </p>
        ))}
      </div>
    </div>
  );
}
