import IconBackspace from '@/public/icons/icon/backspace.svg';

import type { DiffLine } from '../../../types/llmWikiDiff';

interface DeletedBlockPanelProps {
  lines: readonly DiffLine[];
}

/**
 * 블록이 통째로 지워지는 제안의 본문(Figma 17998:46482).
 *
 * 좌우 비교 패널(DiffText)과 구조가 다르다 — 대조할 상대가 없으니 줄 단위 호버가 없고,
 * 대신 패널 안에 "콘텐츠를 삭제함" 고지가 붙는다. 색만으로 삭제를 알리지 않는다는 뜻이라
 * 이 고지를 지우면 안 된다.
 */
export default function DeletedBlockPanel({ lines }: DeletedBlockPanelProps) {
  return (
    <div className="bg-red-1 border-red-40 flex flex-col gap-2 border-l-2 px-3 py-2">
      <p className="text-body-xsmall text-red-50 flex items-center gap-1.5">
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
