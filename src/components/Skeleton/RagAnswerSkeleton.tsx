// 'use client';

// import { RAG_UI_STEPS } from '@/constants/ragStep';
// import RagStepSkeleton from '@/components/Skeleton/RagStepSkeleton';
// import GithubPRStepSkeleton from '@/components/Skeleton/GithubPRStepSkeleton';

// interface RagAnswerSkeletonProps {
//   currentStep: RagUIStepKey | 'manage_pr_context' | null;
//   prList?: PRPayload[];
//   setCurrentStep: (step: RagUIStepKey | 'manage_pr_context' | null) => void;
//   onPRContinue?: (selectedIds: number[]) => void;
// }

// const RagAnswerSkeleton = ({ currentStep, prList = [], setCurrentStep, onPRContinue }: RagAnswerSkeletonProps) => {
//   if (!currentStep) return null;

//   if (currentStep === 'manage_pr_context') {
//     return (
//       <GithubPRStepSkeleton
//         prList={prList}
//         onContinue={(selectedIds) => {
//           onPRContinue?.(selectedIds);
//         }}
//       />
//     );
//   }

//   const step = RAG_UI_STEPS[currentStep];
//   if (!step) return null;

//   return <RagStepSkeleton stepKey={currentStep} label={step.label} Icon={step.Icon} />;
// };

// export default RagAnswerSkeleton;

'use client';

import { RAG_UI_STEPS } from '@/constants/ragStep';
import RagStepSkeleton from '@/components/Skeleton/RagStepSkeleton';

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
