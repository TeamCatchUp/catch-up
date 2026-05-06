'use client';

import { useState } from 'react';

import RewrittenQueryBox from '@/features/chat/components/skeleton/details/RewrittenQueryBox';
import SourceDistributionChips from '@/features/chat/components/skeleton/details/SourceDistributionChips';
import VectorKeywordCodeBox from '@/features/chat/components/skeleton/details/VectorKeywordCodeBox';
import ComplexPlanList from '@/features/chat/components/skeleton/details/ComplexPlanList';
import type { StepRow as StepRowModel } from '@/features/chat/types';
import { cn } from '@/shared/utils/cn';

/**
 * step history의 한 행.
 *
 * Figma: 12861-54620 (normal row), 12861-54638 (active row, 마지막 step)
 *
 * 레이아웃:
 *  - 좌측 22px timeline marker
 *    - normal: 22×22 grey rounded-full, chevron-down icon (16×16) inside
 *    - active: concentric blue/white circle (22→14→7)
 *  - 우측 content (flex-1, pb-4)
 *    - 한 줄 멘트 (15px Medium)
 *    - 노드별 펼침 디테일 박스 (rewritten query / vector / plan list / source chips)
 *
 * row 간 timeline은 marker 아래 vertical line으로 연결.
 * 마지막 row는 line hidden (decorating 끝).
 *
 * 결정 3 (펼침/접힘): 디폴트 펼침, 클릭 시 접기 가능 (chevron rotation).
 */

interface StepRowProps {
  row: StepRowModel;
  isActive: boolean;
  isLast: boolean;
}

const NODE_ICON_BY_RENDERER: Record<string, 'rewrite' | 'vector' | 'plan' | 'chips' | 'plain'> = {
  supervisor: 'plain',
  rewrite: 'rewrite',
  generate_vector_queries: 'plain',
  search_vector_db: 'vector',
  tool_executor: 'vector',
  complex_planner: 'plan',
  standard_agent: 'plain',
  complex_agent: 'plain',
  rerank: 'chips',
};

export default function StepRow({ row, isActive, isLast }: StepRowProps) {
  const [expanded, setExpanded] = useState(true);
  const renderer = NODE_ICON_BY_RENDERER[row.node] ?? 'plain';

  // 한 줄 멘트: in_progress의 reasoning > completed의 reasoning(첫 항목) 우선
  const reasoning =
    row.inProgress?.reasoning ??
    row.completedItems[0]?.reasoning ??
    null;

  const detail = renderDetail({ row, renderer, expanded });
  const hasDetail = detail !== null;

  return (
    <div className="flex items-stretch gap-5">
      {/* Left timeline */}
      <div className="flex w-[22px] shrink-0 flex-col items-center">
        {isActive ? (
          <ActiveMarker />
        ) : (
          <NormalMarker
            expanded={expanded}
            interactive={hasDetail}
            onToggle={() => setExpanded((v) => !v)}
          />
        )}
        {!isLast && <span aria-hidden className="bg-edge-neutral mt-0 w-px flex-1" />}
      </div>

      {/* Right content */}
      <div className="flex min-w-0 flex-1 flex-col items-start gap-2 justify-center pb-4">
        {reasoning && (
          <p className="text-body-small text-content-normal w-full break-words">
            {highlightDocCount(reasoning)}
          </p>
        )}
        {hasDetail && expanded && detail}
      </div>
    </div>
  );
}

/**
 * "N건의 문서를 찾았어요" 같이 reasoning 안의 "N건" 숫자에만 #005EEB(`text-content-primary`) 색상 강조.
 */
function highlightDocCount(text: string): React.ReactNode {
  const regex = /(\d+)(건)/g;
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }
    parts.push(
      <span key={`n-${key++}`} className="text-content-primary">
        {match[1]}
      </span>,
    );
    parts.push(match[2]);
    lastIdx = match.index + match[0].length;
  }
  if (parts.length === 0) return text;
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts;
}

/**
 * 정상 진행 중인 노드 또는 끝난 노드의 timeline marker.
 * chevron-down 아이콘이 위쪽 22×22 원에. 클릭 시 디테일 펼침/접힘.
 */
function NormalMarker({
  expanded,
  interactive,
  onToggle,
}: {
  expanded: boolean;
  interactive: boolean;
  onToggle: () => void;
}) {
  const Icon = (
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      className={cn(
        'text-content-neutral transition-transform duration-150',
        expanded ? 'rotate-0' : '-rotate-90',
      )}
      aria-hidden
    >
      <path
        d="M4 6l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );

  if (!interactive) {
    return (
      <span className="bg-fill-interaction-hover flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full p-0.5">
        {Icon}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      className="bg-fill-interaction-hover hover:bg-fill-strong flex h-[22px] w-[22px] shrink-0 cursor-pointer items-center justify-center rounded-full p-0.5"
    >
      {Icon}
    </button>
  );
}

/**
 * 마지막 active step의 marker (concentric circles).
 * Figma 12861:54640 → 22×22 blue, 14×14 white border, 7×7 white border.
 */
function ActiveMarker() {
  return (
    <span className="bg-fill-primary flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full p-0.5">
      <span className="flex h-[14px] w-[14px] items-center justify-center rounded-full border border-solid border-white p-0.5">
        <span className="h-[7px] w-[7px] rounded-full border border-solid border-white" />
      </span>
    </span>
  );
}

interface RenderDetailParams {
  row: StepRowModel;
  renderer: 'rewrite' | 'vector' | 'plan' | 'chips' | 'plain';
  expanded: boolean;
}

function renderDetail({ row, renderer }: RenderDetailParams): React.ReactNode | null {
  switch (renderer) {
    case 'rewrite': {
      // backend는 string 또는 {query: string} dict로 보낸다 — 정규화는 RewrittenQueryBox에 위임.
      const content = row.completedItems[0]?.content;
      if (content == null) return null;
      return <RewrittenQueryBox query={content} />;
    }
    case 'vector': {
      // backend는 search_vector_db는 array, tool_executor는 {queries: [...]}로 emit한다.
      // 정규화는 VectorKeywordCodeBox에 위임 (entries 0개면 자체적으로 null 반환).
      const content = row.inProgress?.content;
      if (!content) return null;
      return <VectorKeywordCodeBox queries={content} />;
    }
    case 'plan': {
      if (row.completedItems.length === 0) return null;
      return <ComplexPlanList items={row.completedItems} />;
    }
    case 'chips': {
      const content = row.completedItems[0]?.content;
      if (!content || typeof content !== 'object') return null;
      const dist = (content as { source_distribution?: unknown }).source_distribution;
      if (!dist) return null;
      return <SourceDistributionChips distribution={dist} />;
    }
    case 'plain':
    default:
      return null;
  }
}
