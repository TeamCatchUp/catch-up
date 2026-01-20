'use client';

import { RAG_UI_STEPS } from '@/constants/ragStep';
import RagStepSkeleton from '@/components/Skeleton/RagStepSkeleton';
import GithubPRStepSkeleton from '@/components/Skeleton/GithubPRStepSkeleton';

interface RagAnswerSkeletonProps {
  currentStep: RagStepKey | null;
  hasGithubPR: boolean;
  setCurrentStep: (step: RagStepKey | null) => void;
}

const RagAnswerSkeleton = ({ currentStep, hasGithubPR, setCurrentStep }: RagAnswerSkeletonProps) => {
  if (!currentStep) return null;

  if (currentStep === 'github_pr_mcp') {
    return (
      <GithubPRStepSkeleton
        onContinue={() => {
          if (hasGithubPR) {
            setCurrentStep('grade');
          } else {
            setCurrentStep('generate');
          }
        }}
      />
    );
  }

  const step = RAG_UI_STEPS[currentStep];
  if (!step) return null;

  return <RagStepSkeleton stepKey={currentStep} label={step.label} Icon={step.Icon} />;
};

export default RagAnswerSkeleton;
