'use client';

import { useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';

import CloseIcon from '@/public/icons/icon/cancel.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogOverlay, DialogPortal } from '@/shared/components/ui/dialog';

import { ADMIN_GUIDE_STEPS, TOTAL_STEPS } from '../constants/adminGuide';

interface AdminGuideModalProps {
  onDismiss: () => void;
}

const TRANSITION_MS = 200;

export default function AdminGuideModal({ onDismiss }: AdminGuideModalProps) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  const currentStep = ADMIN_GUIDE_STEPS[step];
  const isFirstStep = step === 0;
  const isLastStep = step === TOTAL_STEPS - 1;

  const handleCloseAttempt = () => {
    setShowCloseConfirm(true);
  };

  const handleConfirmDismiss = () => {
    onDismiss();
  };

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
          {showCloseConfirm ? (
            <CloseConfirmContent onDismiss={handleConfirmDismiss} onNavigate={handleNavigateIntegration} />
          ) : (
            <GuideContent
              step={step}
              currentStep={currentStep}
              isFirstStep={isFirstStep}
              isLastStep={isLastStep}
              isTransitioning={isTransitioning}
              onClose={handleCloseAttempt}
              onNext={handleNext}
              onPrev={handlePrev}
            />
          )}
        </div>
      </DialogPortal>
    </Dialog>
  );
}

/** 가이드 모달 본문 */
function GuideContent({
  step,
  currentStep,
  isFirstStep,
  isLastStep,
  isTransitioning,
  onClose,
  onNext,
  onPrev,
}: {
  step: number;
  currentStep: (typeof ADMIN_GUIDE_STEPS)[number];
  isFirstStep: boolean;
  isLastStep: boolean;
  isTransitioning: boolean;
  onClose: () => void;
  onNext: () => void;
  onPrev: () => void;
}) {
  return (
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
            onClick={onClose}
            className="hover:bg-fill-interaction-hover text-content-alternative flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full"
          >
            <CloseIcon className="size-5" />
          </button>
        </div>

        {/* 일러스트 이미지 */}
        <div className="relative h-40 w-full overflow-hidden rounded-lg">
          <Image src={currentStep.image} alt={currentStep.title.join(' ')} fill className="object-cover dark:hidden" />
          <Image
            src={currentStep.image.replace('/light/', '/dark/')}
            alt={currentStep.title.join(' ')}
            fill
            className="hidden object-cover dark:block"
          />
        </div>

        {/* 본문 텍스트 */}
        <div className="text-body-small text-content-alternative">
          {step === 2 ? <Step3Body /> : <p className="whitespace-pre-line">{currentStep.body}</p>}
        </div>
      </div>

      {/* Footer: 페이지네이션 + 버튼 */}
      <div className="border-edge-normal flex shrink-0 items-center justify-between border-t pt-5">
        {/* Pagination Dots */}
        <div className="flex gap-2.5 px-2">
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <div
              key={i}
              className={`size-2.5 rounded-full ${i === step ? 'bg-edge-primary' : 'bg-fill-interaction-hover'}`}
            />
          ))}
        </div>

        {/* Navigation Buttons */}
        <div className="flex gap-3">
          <Button variant="box-outline-gray" size="lg" className={isFirstStep ? 'invisible' : ''} onClick={onPrev}>
            이전
          </Button>
          <Button variant="box-solid-primary" size="lg" onClick={onNext}>
            {isLastStep ? '협업 툴 연동하기' : '다음'}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** 닫기 확인 모달 본문 */
function CloseConfirmContent({ onDismiss, onNavigate }: { onDismiss: () => void; onNavigate: () => void }) {
  return (
    <div className="shadow-modal border-edge-strong bg-fill-normal flex w-100 flex-col gap-3 overflow-clip rounded-2xl border p-5">
      {/* 텍스트 */}
      <div className="flex flex-col gap-3">
        <p className="text-heading-medium text-status-cautionary">
          원활한 캐치업 이용을 위해선
          <br />
          최소 1개 이상의 협업 툴을 연동해야 해요.
        </p>
        <p className="text-body-small text-content-neutral">
          지금은 질문을 시작할 준비가 안 됐어요.
          <br />
          협업툴을 선택하고 진행해주세요.
        </p>
      </div>

      {/* 버튼 */}
      <div className="flex items-center justify-end gap-2.5">
        <Button variant="capsule-outline-mono" size="lg" onClick={onDismiss}>
          괜찮아요
        </Button>
        <Button variant="capsule-solid-primary" size="lg" onClick={onNavigate}>
          연동할게요
        </Button>
      </div>
    </div>
  );
}

/** 3단계 본문: 번호 리스트 + 부가 설명 */
function Step3Body() {
  return (
    <div className="flex flex-col gap-1.5">
      <p>1. 최소 1개 커넥터 연동은 필수예요.</p>
      <p>2. 루트 어드민도 각 협업툴에서 본인 계정을 등록해주세요.</p>
      <p>3. 사내 사용자의 80% 이상이 등록되면, 임베딩을 켤 수 있어요.</p>
      <p className="mt-2">
        *사용자가 이용하는 협업 툴 계정을 모르면
        <br />
        툴 간 사용자 매핑이 불완전해져서,
        <br />
        특정 사람의 작업이 빠지거나 결과가 달라질 수 있어요.
      </p>
    </div>
  );
}
