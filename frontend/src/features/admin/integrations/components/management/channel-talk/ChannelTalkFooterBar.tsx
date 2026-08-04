import IconAddSmall from '@/public/icons/icon/add_small.svg';
import IconArrowRight2 from '@/public/icons/icon/arrow_right2.svg';
import { Button } from '@/shared/components/ui/button';

interface ChannelTalkFooterBarProps {
  channelCount: number;
  documentCount: number;
  onAddChannel: () => void;
  onProceed: () => void;
}

/**
 * 채널톡 연결 관리 하단 고정 바.
 * Figma `17345:84633` — padding 12/32, gap 6, 상단 경계선만 있고 배경은 없다.
 *
 * 집계에서 **숫자만** `#3385FF`로 강조된다(`{ts1}5{/ts1}개 채널`).
 * 실패 건수의 50,000+ 규칙은 여기 적용하지 않는다(사용자 결정).
 *
 * 버튼은 Figma의 Box Button medium 두 종이다.
 *   채널 추가   Solid Blue(Secondary) = box-soft-primary
 *   임베딩하기  Solid Blue(Primary)   = box-solid-primary
 *
 * 임베딩하기에는 활성 조건이 없다(사용자 결정). secret 입력 여부나
 * `connectionStatus`로 막지 않는다 — 검증은 다음 단계와 서버가 한다.
 * 다음 단계의 {@link ChannelTalkEmbeddingFooterBar}는 선택 0개면 비활성인데,
 * 그건 임베딩할 대상 자체가 없는 경우라 성격이 다르다.
 */
export default function ChannelTalkFooterBar({
  channelCount,
  documentCount,
  onAddChannel,
  onProceed,
}: ChannelTalkFooterBarProps) {
  // 실측: 줄바꿈 없이는 1024부터 버튼이 잘렸다(900에서 125px) — 좁으면 버튼 묶음이 아랫줄로
  return (
    <div className="border-line-normal-neutral flex flex-wrap items-center gap-x-1.5 gap-y-2 border-t px-8 py-3">
      <p className="text-body-small text-text-normal-normal shrink-0">
        <span className="text-text-primary-assistive">{channelCount}</span>개 채널
      </p>
      <span aria-hidden="true" className="bg-dim-black-25 size-1 shrink-0 rounded-full" />
      <p className="text-body-small text-text-normal-normal min-w-0 flex-1 truncate">
        <span className="text-text-primary-assistive">{documentCount}</span>개 도큐먼트 연결됨
      </p>

      <div className="flex shrink-0 items-center gap-3">
        <Button variant="box-soft-primary" size="md" onClick={onAddChannel}>
          <IconAddSmall className="size-5" />
          채널 추가
        </Button>
        <Button variant="box-soft-primary" size="md" onClick={onProceed} className="text-heading-small">
          임베딩하기
          <IconArrowRight2 className="size-6" />
        </Button>
      </div>
    </div>
  );
}
