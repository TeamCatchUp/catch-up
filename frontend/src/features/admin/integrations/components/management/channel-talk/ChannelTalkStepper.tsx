import IconArrowBack from '@/public/icons/icon/arrow_back.svg';
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
  /** 단계 칩 클릭 — 양방향 이동 */
  onStepChange: (step: ChannelTalkStep) => void;
  /** 임베딩 관리 탭으로 돌아간다 */
  onBack: () => void;
}

/**
 * 채널톡 2스텝 진행 표시.
 *
 * 활성/비활성은 **회색 명도 차이**로만 구분한다. primary 색을 쓰지 않는다.
 * 칩의 알파값에 대응하는 토큰이 코드에 없다(알파 오버레이 전환 미적용).
 * 흰 배경 위 합성값이 neutral 램프와 거의 일치해 line 계열 토큰으로 낸다 —
 * fill-interaction-* 은 상태 레이어라 장식에 쓰면 나중 전환 때 끌려간다.
 *
 * 단계 칩은 클릭으로 양방향 이동한다(사용자 지시 2026-08-04). 하단 바
 * [임베딩하기]에 활성 조건이 없으므로 ①→② 이동에도 조건을 두지 않는다.
 * Figma에 hover·pressed가 없어 커서만 바꾸고 색은 건드리지 않는다.
 *
 * 되돌아오면 스텝 ①은 다시 마운트되어 서버 상태에서 폼을 새로 만든다 —
 * 저장 전 입력값은 남지 않는다. 하단 바로 넘어갈 때도 마찬가지다.
 */
export default function ChannelTalkStepper({ current, onStepChange, onBack }: ChannelTalkStepperProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <ol className="flex items-center gap-1.5">
        {STEPS.map((step, index) => {
          const active = step.value === current;

          return (
            <li key={step.value} aria-current={active ? 'step' : undefined} className="flex items-center gap-1.5">
              {index > 0 && <IconArrowRight2 className="text-icon-normal-assistive size-6 shrink-0" />}
              <button
                type="button"
                onClick={() => onStepChange(step.value)}
                // 현재 단계는 눌러도 갈 곳이 없다 — 초점은 받되 커서로 그 사실을 알린다
                className={cn(
                  'flex items-center gap-2 rounded-lg px-2 py-1.5',
                  active
                    ? 'bg-fill-normal-strong border-line-normal-assistive cursor-default border'
                    : 'cursor-pointer',
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'text-heading-small flex size-6 items-center justify-center rounded-lg',
                    active
                      ? 'bg-line-normal-normal text-text-normal-neutral'
                      : 'bg-line-normal-assistive text-text-normal-alternative',
                  )}
                >
                  {index + 1}
                </span>
                <span
                  className={cn('text-body-small', active ? 'text-text-normal-normal' : 'text-text-normal-alternative')}
                >
                  {step.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <Button variant="text-secondary-mono" size="md" onClick={onBack} className="text-heading-small shrink-0 gap-1.5">
        <IconArrowBack className="size-5" />
        임베딩 관리로
      </Button>
    </div>
  );
}
