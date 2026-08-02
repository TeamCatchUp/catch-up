import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { Button } from '@/shared/components/ui/button';

interface ChannelTalkFooterBarProps {
  channelCount: number;
  documentCount: number;
  /** 임베딩 단계로 넘어갈 수 있는지 */
  canProceed: boolean;
  onAddChannel: () => void;
  onProceed: () => void;
}

/**
 * 채널톡 연결 관리 하단 고정 바.
 * Figma `17363:100408` — 780×60, 집계 좌측 · 액션 우측, 가운데 4×4 점 구분자.
 *
 * 집계에는 실패 건수의 50,000+ 규칙을 적용하지 않는다(사용자 결정).
 */
export default function ChannelTalkFooterBar({
  channelCount,
  documentCount,
  canProceed,
  onAddChannel,
  onProceed,
}: ChannelTalkFooterBarProps) {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex h-15 items-center justify-between gap-4 border-t px-8">
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="text-body-small text-text-normal-neutral">{channelCount}개 채널</span>
        <span aria-hidden="true" className="bg-line-normal-neutral size-1 shrink-0 rounded-full" />
        <span className="text-body-small text-text-normal-neutral truncate">{documentCount}개 도큐먼트 연결됨</span>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <Button variant="box-outline-gray" size="md" onClick={onAddChannel}>
          <IconAddSmall className="size-5" />
          채널 추가
        </Button>
        <Button variant="box-solid-primary" size="md" onClick={onProceed} disabled={!canProceed}>
          임베딩하기
          <IconArrowRight2 className="size-5" />
        </Button>
      </div>
    </div>
  );
}
