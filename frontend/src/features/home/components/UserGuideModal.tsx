'use client';

import { useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';

import CloseIcon from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogOverlay, DialogPortal } from '@/shared/components/ui/dialog';

import { USER_GUIDE_STEPS, USER_GUIDE_TOTAL_STEPS } from '../constants/userGuide';

interface UserGuideModalProps {
  onDismiss: () => void;
}

const TRANSITION_MS = 200;

export default function UserGuideModal({ onDismiss }: UserGuideModalProps) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const currentStep = USER_GUIDE_STEPS[step];
  const isFirstStep = step === 0;
  const isLastStep = step === USER_GUIDE_TOTAL_STEPS - 1;

  const handleNavigateIntegration = () => {
    onDismiss();
    router.push('/mypage/integrations');
  };

  const changeStep = (next: number) => {
    setIsTransitioning(true);
    setTimeout(() => {
      setStep(next);
      setIsTransitioning(false);
    }, TRANSITION_MS);
  };

  const handleNext = () => {
    if (isLastStep) {
      handleNavigateIntegration();
    } else {
      changeStep(step + 1);
    }
  };

  const handlePrev = () => {
    changeStep(step - 1);
  };

  return (
    <Dialog open onOpenChange={() => {}}>
      <DialogPortal>
        <DialogOverlay />
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="shadow-modal border-edge-strong bg-fill-normal flex h-135.75 w-108.75 flex-col overflow-clip rounded-2xl border p-6">
            {/* 콘텐츠 영역 */}
            <div
              className={`flex min-h-0 flex-1 flex-col gap-5 overflow-hidden transition-opacity duration-200 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}
            >
              {/* Header: 제목 + X 닫기 */}
              <div className="flex items-start justify-between">
                <h2 className="text-heading-large text-content-strong">
                  {currentStep.title.map((line, i) => (
                    <span key={i}>
                      {i > 0 && <br />}
                      {line}
                    </span>
                  ))}
                </h2>
                <button
                  type="button"
                  onClick={onDismiss}
                  className="hover:bg-fill-interaction-hover text-content-alternative flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full"
                >
                  <CloseIcon className="size-5" />
                </button>
              </div>

              {/* 일러스트 이미지 */}
              <div className="relative h-40 w-full overflow-hidden rounded-lg">
                <Image
                  src={currentStep.image}
                  alt={currentStep.title.join(' ')}
                  fill
                  className="object-cover dark:hidden"
                />
                <Image
                  src={currentStep.image.replace('/light/', '/dark/')}
                  alt={currentStep.title.join(' ')}
                  fill
                  className="hidden object-cover dark:block"
                />
              </div>

              {/* 본문 텍스트 */}
              <div className="text-body-small text-content-alternative">
                <p className="whitespace-pre-line">{currentStep.body}</p>
              </div>
            </div>

            {/* Footer: 페이지네이션 + 버튼 */}
            <div className="border-edge-normal flex shrink-0 items-center justify-between border-t pt-5">
              {/* Pagination Dots */}
              <div className="flex gap-2.5 self-center px-2">
                {Array.from({ length: USER_GUIDE_TOTAL_STEPS }).map((_, i) => (
                  <div
                    key={i}
                    className={`size-2.5 rounded-full ${i === step ? 'bg-blue-30' : 'bg-fill-interaction-hover'}`}
                  />
                ))}
              </div>

              {/* Navigation Buttons */}
              <div className="flex gap-3">
                <Button
                  variant="box-outline-gray"
                  size="lg"
                  className={isFirstStep ? 'invisible' : ''}
                  onClick={handlePrev}
                >
                  이전
                </Button>
                <Button variant="box-solid-primary" size="lg" onClick={handleNext}>
                  {isLastStep ? '시작하기' : '다음'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </DialogPortal>
    </Dialog>
  );
}
