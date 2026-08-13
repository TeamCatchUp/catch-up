import { cn } from '@/shared/utils/cn';

interface OnboardingFieldLabelProps {
  label: string;
  /** 시안의 필수 점 — 검증 실패 표시는 시안에 없어 시각만 있다 */
  required?: boolean;
  className?: string;
}

// 온보딩 폼 라벨 + 필수 점
export default function OnboardingFieldLabel({ label, required, className }: OnboardingFieldLabelProps) {
  return (
    <div className={cn('flex items-start gap-1', className)}>
      <span className="text-heading-small text-text-normal-normal">{label}</span>
      {required && <span className="bg-status-destructive mt-1 size-[5px] shrink-0 rounded-full" aria-label="필수 입력" />}
    </div>
  );
}
