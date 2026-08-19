import { Button } from '@/shared/components/ui/button';

interface OnboardingActionBarProps {
  /** 없으면 이전 버튼을 그리지 않는다 — 1단계는 시안에 다음 버튼만 있다 */
  backLabel?: string;
  onBack?: () => void;
  nextLabel: string;
  onNext?: () => void;
  /** 필수 입력이 덜 찼을 때 잠근다 — 보낼 수 없는 요청을 만들지 않는다 */
  nextDisabled?: boolean;
}

// 온보딩 3단계가 공유하는 하단 액션 바. 콘텐츠 패딩 밖의 형제라 상단 테두리가 전폭을 긋는다
// 스크롤해도 하단에 남는다 — 배경이 불투명해야 본문이 비쳐 보이지 않는다
export default function OnboardingActionBar({
  backLabel,
  onBack,
  nextLabel,
  onNext,
  nextDisabled = false,
}: OnboardingActionBarProps) {
  return (
    <div className="border-line-normal-assistive bg-fill-normal-assistive z-base sticky bottom-0 flex h-13 shrink-0 items-center justify-end gap-3 border-t px-16">
      {backLabel && (
        <Button variant="box-outline-gray" size="md" onClick={onBack}>
          {backLabel}
        </Button>
      )}
      <Button variant="box-solid-primary" size="md" onClick={onNext} disabled={nextDisabled}>
        {nextLabel}
      </Button>
    </div>
  );
}
