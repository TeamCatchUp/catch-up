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
  /** 임베딩 관리 탭으로 돌아간다 */
  onBack: () => void;
}

/**
 * 채널톡 2스텝 진행 표시.
 * Figma `17332:84389` — 단계 컨테이너 padding 6/8, gap 8, radius 8, 사이 gap 6.
 *
 * 활성/비활성은 **회색 명도 차이**로만 구분한다. primary 색을 쓰지 않는다.
 *   활성   컨테이너 #F7F7F8 + stroke #F4F4F5 / 칩 rgba(30,33,36,.12) / 라벨 #33363D
 *   비활성 컨테이너 투명            / 칩 rgba(30,33,36,.06) / 라벨 #6D7882
 *
 * 칩의 알파값에 대응하는 토큰이 코드에 없다(알파 오버레이 전환 미적용).
 * 흰 배경 위 합성값이 neutral 램프와 거의 일치해 line 계열 토큰으로 낸다 —
 * fill-interaction-* 은 상태 레이어라 장식에 쓰면 나중 전환 때 끌려간다.
 */
export default function ChannelTalkStepper({ current, onBack }: ChannelTalkStepperProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <ol className="flex items-center gap-1.5">
        {STEPS.map((step, index) => {
          const active = step.value === current;

          return (
            <li key={step.value} aria-current={active ? 'step' : undefined} className="flex items-center gap-1.5">
              {index > 0 && <IconArrowRight2 className="text-icon-normal-assistive size-6 shrink-0" />}
              <span
                className={cn(
                  'flex items-center gap-2 rounded-lg px-2 py-1.5',
                  active && 'bg-fill-normal-strong border-line-normal-assistive border',
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
              </span>
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
