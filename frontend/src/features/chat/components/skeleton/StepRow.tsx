'use client';

import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import ComplexPlanList from '@/features/chat/components/skeleton/details/ComplexPlanList';
import RewrittenQueryBox from '@/features/chat/components/skeleton/details/RewrittenQueryBox';
import SourceDistributionChips from '@/features/chat/components/skeleton/details/SourceDistributionChips';
import VectorKeywordCodeBox from '@/features/chat/components/skeleton/details/VectorKeywordCodeBox';
import type { StepRow as StepRowModel } from '@/features/chat/types';
import { collapseExpand, crossfade, MotionState } from '@/shared/motion';
import { cn } from '@/shared/utils/cn';

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

  const reasoning = row.inProgress?.reasoning ?? row.completedItems[0]?.reasoning ?? null;

  const detail = renderDetail({ row, renderer, expanded });
  const hasDetail = detail !== null;

  return (
    <div className="flex items-stretch gap-5">
      <div className="flex w-[22px] shrink-0 flex-col items-center">
        <AnimatePresence mode="wait" initial={false}>
          {isActive ? (
            <motion.span
              key="active"
              variants={crossfade}
              initial={MotionState.Hidden}
              animate={MotionState.Visible}
              exit={MotionState.Exit}
              className="flex"
            >
              <ActiveMarker />
            </motion.span>
          ) : (
            <motion.span
              key="normal"
              variants={crossfade}
              initial={MotionState.Hidden}
              animate={MotionState.Visible}
              exit={MotionState.Exit}
              className="flex"
            >
              <NormalMarker
                expanded={expanded}
                interactive={hasDetail}
                onToggle={() => setExpanded((v) => !v)}
              />
            </motion.span>
          )}
        </AnimatePresence>
        {!isLast && <span aria-hidden className="bg-edge-neutral mt-0 w-px flex-1" />}
      </div>

      <div className="flex min-w-0 flex-1 flex-col items-start gap-2 justify-center pb-4">
        {reasoning && (
          <p className="text-body-small text-content-normal w-full break-words">
            {highlightDocCount(reasoning)}
          </p>
        )}
        <AnimatePresence initial={true}>
          {hasDetail && expanded && (
            <motion.div
              key="detail"
              variants={collapseExpand}
              initial={MotionState.Hidden}
              animate={MotionState.Visible}
              exit={MotionState.Exit}
              className="w-full overflow-hidden"
            >
              {detail}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/** reasoning 안의 "N건" 숫자만 primary 색상으로 강조한다. */
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
      const content = row.completedItems[0]?.content;
      if (content == null) return null;
      return <RewrittenQueryBox query={content} />;
    }
    case 'vector': {
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
