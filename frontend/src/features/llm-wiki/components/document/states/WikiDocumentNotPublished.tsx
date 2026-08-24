'use client';

import { motion } from 'motion/react';

import IconEmptyDocument from '@/public/icons/icon/empty_document.svg';
import { Button } from '@/shared/components/ui/button';
import { usePrefersReducedMotion } from '@/shared/hooks/usePrefersReducedMotion';
import { MotionState, panelStateFadeIn, panelStateFadeInReduced } from '@/shared/motion';

interface WikiDocumentNotPublishedProps {
  /** 검토 큐로 보내는 진입점. 이 문서의 계류 안건이 미리 골라진다 */
  onOpenReviewQueue: () => void;
}

/**
 * 첫 판이 아직 발행되지 않은 문서의 안내. 빈 표 안내와 같은 일러스트·타이포를 쓴다.
 * 경로 이름의 공급원이 문서 응답이라 헤더는 마디 없이 셸만 남는다.
 */
export default function WikiDocumentNotPublished({ onOpenReviewQueue }: WikiDocumentNotPublishedProps) {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <section className="flex min-h-full flex-col">
      <div aria-hidden className="border-line-normal-neutral h-13 shrink-0 border-b" />

      <motion.div
        variants={prefersReducedMotion ? panelStateFadeInReduced : panelStateFadeIn}
        initial={MotionState.Hidden}
        animate={MotionState.Visible}
        className="flex flex-1 flex-col items-center justify-center gap-5"
      >
        <IconEmptyDocument aria-hidden className="h-13.75 w-16 shrink-0" />

        <div className="flex flex-col items-center gap-1">
          <p className="text-body-small text-text-normal-normal text-center">아직 첫 판이 발행되지 않았어요</p>
          <p className="text-body-xsmall text-text-normal-assistive text-center">첫 변경안이 검토를 기다리고 있어요</p>
        </div>

        <Button variant="box-outline-gray" size="md" onClick={onOpenReviewQueue}>
          검토 큐에서 보기
        </Button>
      </motion.div>
    </section>
  );
}
