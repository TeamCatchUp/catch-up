'use client';

import RagStepSkeleton from '@/features/chat/components/skeleton/RagStepSkeleton';
import { RAG_UI_STEPS } from '@/features/chat/constants/steps';
import type { RagUIStepKey } from '@/features/chat/types';

interface Props {
  currentStep: RagUIStepKey;
}

export default function RagAnswerSkeleton({ currentStep }: Props) {
  if (currentStep === 'manage_pr_context') {
    return null;
  }

  const step = RAG_UI_STEPS[currentStep];
  if (!step) return null;

  return <RagStepSkeleton stepKey={currentStep} label={step.label} Icon={step.Icon} />;
}
