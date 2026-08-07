import { cn } from '@/shared/utils/cn';

import type { DiffLine } from '../../../types/llmWikiDiff';

interface DiffTextProps {
  lines: readonly DiffLine[];
  tone: 'removed' | 'added';
}

// 패널·세로 바·줄 호버 색은 Figma 실측(감사 §9 부록), 단어 강조 색만 프론트 결정이다.
const TONE_STYLES = {
  removed: { panel: 'bg-red-1 border-red-40', line: 'hover:bg-red-5', emphasized: 'bg-red-10' },
  added: { panel: 'bg-green-5 border-green-60', line: 'hover:bg-green-10', emphasized: 'bg-green-20' },
} as const;

/**
 * diff 패널 한 쪽. 줄 단위 호버 하이라이트(패널별 독립, 기능 없음)와
 * modified 카드의 단어 강조(진한 배경)를 렌더한다. 빈 줄도 높이를 가져야
 * 문단 간격이 보존된다 — min-h가 그 역할이다.
 */
export default function DiffText({ lines, tone }: DiffTextProps) {
  const styles = TONE_STYLES[tone];

  return (
    <div className={cn('flex-1 border-l-2 py-1', styles.panel)}>
      {lines.map((line, lineIndex) => (
        <p
          key={lineIndex}
          className={cn('text-body-small text-text-normal-normal min-h-6.5 px-3 py-2', styles.line)}
        >
          {line.segments.map((segment, segmentIndex) => (
            <span key={segmentIndex} className={cn(segment.emphasized && styles.emphasized)}>
              {segment.text}
            </span>
          ))}
        </p>
      ))}
    </div>
  );
}
