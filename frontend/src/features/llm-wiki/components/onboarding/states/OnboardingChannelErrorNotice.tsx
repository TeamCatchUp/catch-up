import { Button } from '@/shared/components/ui/button';

interface OnboardingChannelErrorNoticeProps {
  /** 없으면 문구만 — 재시도 동선이 없는 화면에서 죽은 버튼을 만들지 않기 위해 optional이다 */
  onRetry?: () => void;
}

/**
 * 채널 목록 조회 실패 안내.
 * 빈 목록으로 렌더하면 "연결할 채널이 없다"로 오해하므로 실패를 명시한다.
 */
export default function OnboardingChannelErrorNotice({ onRetry }: OnboardingChannelErrorNoticeProps) {
  return (
    <div
      role="alert"
      className="border-line-normal-assistive bg-fill-normal-strong flex flex-col items-center gap-4 rounded-xl border px-6 py-16"
    >
      <p className="text-body-small text-status-destructive">
        채널 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.
      </p>
      {onRetry && (
        <Button variant="box-outline-gray" size="md" onClick={onRetry}>
          다시 시도
        </Button>
      )}
    </div>
  );
}
