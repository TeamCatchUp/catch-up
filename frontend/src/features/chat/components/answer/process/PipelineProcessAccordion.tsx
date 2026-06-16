'use client';

import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import type { PipelineEvent } from '@/features/chat/types';
import { buildInlineSteps } from '@/features/chat/utils/process/buildInlineSteps';
import ArrowDown from '@/public/icons/icon/arrow_down.svg';
import { collapseExpand, fadeInUp, MotionState, staggerListContainer } from '@/shared/motion';
import { cn } from '@/shared/utils/cn';

import PipelineStepItem from './PipelineStepItem';

interface PipelineProcessAccordionProps {
  pipelineResult: PipelineEvent[] | null | undefined;
  sourceCount: number;
}

/**
 * 답변 본문 하단의 생성 과정 인라인 아코디언.
 * - 헤더(자료 수 + 화살표)는 하단에 위치, 펼치면 단계 목록이 그 위에 나타남
 * - pipeline_result가 없거나 생성 과정이 없으면 기존 텍스트 줄로 fallback
 */
export default function PipelineProcessAccordion({ pipelineResult, sourceCount }: PipelineProcessAccordionProps) {
  const [expanded, setExpanded] = useState(false);
  const steps = useMemo(() => buildInlineSteps(pipelineResult), [pipelineResult]);
  const headerText = `질문과 연관된 ${sourceCount}개의 핵심 자료를 선별했어요.`;

  if (steps.length === 0) {
    return <div className="text-body-small text-text-normal-assistive">{headerText}</div>;
  }

  return (
    <div className="flex w-full flex-col gap-2.5">
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="panel"
            variants={collapseExpand}
            initial={MotionState.Hidden}
            animate={MotionState.Visible}
            exit={MotionState.Exit}
            className="w-full overflow-hidden"
          >
            <motion.div
              variants={staggerListContainer}
              initial={MotionState.Hidden}
              animate={MotionState.Visible}
              className="flex w-full flex-col gap-1"
            >
              {steps.map((step, idx) => (
                <motion.div key={step.kind} variants={fadeInUp}>
                  <PipelineStepItem step={step} isLast={idx === steps.length - 1} />
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-fit cursor-pointer items-center gap-2.5"
      >
        <span className="text-body-small text-text-normal-assistive">{headerText}</span>
        <ArrowDown
          aria-hidden
          className={cn(
            'text-icon-normal-alternative h-5.5 w-5.5 transition-transform duration-200',
            expanded && 'rotate-180',
          )}
        />
      </button>
    </div>
  );
}
