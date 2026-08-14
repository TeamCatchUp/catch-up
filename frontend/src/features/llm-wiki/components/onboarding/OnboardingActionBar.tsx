import { Button } from '@/shared/components/ui/button';

interface OnboardingActionBarProps {
  /** 없으면 이전 버튼을 그리지 않는다 — 1단계는 시안에 다음 버튼만 있다 */
  backLabel?: string;
  onBack?: () => void;
  nextLabel: string;
  onNext?: () => void;
}

// 온보딩 3단계가 공유하는 하단 액션 바. 콘텐츠 패딩 밖의 형제라 상단 테두리가 전폭을 긋는다
export default function OnboardingActionBar({ backLabel, onBack, nextLabel, onNext }: OnboardingActionBarProps) {
  return (
    <div className="border-line-normal-neutral flex justify-end gap-3 border-t px-16 py-2">
      {backLabel && (
        <Button variant="box-outline-gray" size="md" onClick={onBack}>
          {backLabel}
        </Button>
      )}
      <Button variant="box-solid-primary" size="md" onClick={onNext}>
        {nextLabel}
      </Button>
    </div>
  );
}
