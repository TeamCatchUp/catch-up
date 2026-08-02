import IconArrowLeft from '@/public/icons/icon/arrow_left.svg';
import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

export type ChannelTalkStep = 'connect' | 'embed';

const STEPS: readonly { value: ChannelTalkStep; label: string }[] = [
  { value: 'connect', label: '채널 연결 관리' },
  { value: 'embed', label: '임베딩하기' },
];

interface ChannelTalkStepperProps {
  current: ChannelTalkStep;
  /** 임베딩 관리 탭으로 돌아간다 */
  onBack: () => void;
}

/**
 * 채널톡 2스텝 진행 표시.
 * Figma `17363:100283` — 숫자 칩 24, 라벨 x40, 단계 사이 `icon/arrow_right2` 24.
 */
export default function ChannelTalkStepper({ current, onBack }: ChannelTalkStepperProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <ol className="flex items-center">
        {STEPS.map((step, index) => {
          const active = step.value === current;

          return (
            <li key={step.value} aria-current={active ? 'step' : undefined} className="flex items-center">
              {index > 0 && <IconArrowRight2 className="text-icon-normal-assistive mx-1.5 size-6 shrink-0" />}
              <span className="flex items-center gap-2 px-2 py-1.5">
                <span
                  aria-hidden="true"
                  className={cn(
                    'text-body-small flex size-6 items-center justify-center rounded-md',
                    active
                      ? 'bg-fill-primary-normal-normal text-white'
                      : 'bg-fill-normal-strong text-text-normal-assistive',
                  )}
                >
                  {index + 1}
                </span>
                <span
                  className={cn(
                    'text-body-small',
                    active ? 'text-text-normal-normal' : 'text-text-normal-assistive',
                  )}
                >
                  {step.label}
                </span>
              </span>
            </li>
          );
        })}
      </ol>

      <Button variant="text-secondary-mono" size="md" onClick={onBack} className="shrink-0 gap-1.5">
        <IconArrowLeft className="size-5" />
        임베딩 관리로
      </Button>
    </div>
  );
}
