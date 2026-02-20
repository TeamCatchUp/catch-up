'use client';

import LockIcon from '@/public/icons/icon/lock_filled.svg';
import CatchUpIcon from '@/public/icons/logo/logo_catchup.svg';
import CatchUpLetter from '@/public/icons/logo/logo_catchup_letter_blue.svg';
import { Button } from '@/shared/components/ui/button';

interface WelcomeStepProps {
  onStart: () => void;
  isLoading?: boolean;
}

export function WelcomeStep({ onStart, isLoading }: WelcomeStepProps) {
  return (
    <div className="flex size-full flex-col items-center justify-center">
      <div className="flex w-[440px] flex-col items-start gap-10 pb-[120px]">
        {/* 텍스트 섹션 */}
        <div className="flex w-full flex-col items-start gap-9">
          <h1 className="text-display-large text-gray-80 tracking-tight">반갑습니다!</h1>

          <div className="flex flex-col items-start gap-1.5">
            <p className="text-display-large text-gray-80 tracking-tight">이제 팀의 기억이 사라지지 않도록 </p>
            <div className="flex items-center gap-1.5">
              <div className="flex items-center gap-2">
                <div className="border-neutral-3 flex size-[55px] shrink-0 flex-col items-center justify-center overflow-clip rounded-2xl border bg-white p-2">
                  <CatchUpIcon className="w-full shrink-0" />
                </div>
                <CatchUpLetter className="h-[31px] w-[133px]" />
              </div>
              <span className="text-display-large text-gray-80 tracking-tight">이 도와드릴게요.</span>
            </div>
          </div>
        </div>

        {/* 액션 섹션 */}
        <div className="flex w-full flex-col items-start gap-2.5">
          <div className="flex w-full items-center gap-1.5">
            <div className="size-[22px] shrink-0 overflow-clip">
              <LockIcon className="size-full text-gray-30" />
            </div>
            <span className="text-body-medium text-gray-80 tracking-tight">소속 조직의 계정으로 안전하게 로그인하세요.</span>
          </div>
          <Button
            variant="box-solid-primary"
            size="lg"
            onClick={onStart}
            disabled={isLoading}
            className="h-[46px] w-full"
          >
            SSO 통합 로그인하기
          </Button>
        </div>
      </div>
    </div>
  );
}
