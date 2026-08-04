'use client';

import { Button } from '@/shared/components/ui/button';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

interface ChannelTalkEmbeddingFooterBarProps {
  channelCount: number;
  documentCount: number;
  allSelected: boolean;
  /** 제출 요청이 진행 중 — 버튼을 잠그고 라벨로 알린다 */
  isSubmitting?: boolean;
  onToggleAll: () => void;
  onEmbed: () => void;
}

/**
 * 임베딩 대상 선택 단계(스텝 ②)의 하단 바 — 전체 선택 체크박스 + 집계 + 제출 버튼.
 * 스텝 ①의 {@link ChannelTalkFooterBar}(채널 추가 + 진행 버튼)와는 다른 컴포넌트다.
 *
 * 체크 표시는 **전부 선택했을 때만** 들어온다 — 일부 선택의 indeterminate 표시는
 * 쓰지 않는다(사용자 결정 2026-08-04). 라벨 텍스트는 버튼 안에 있어 텍스트를
 * 눌러도 토글되고, 접근성 이름도 이 텍스트가 된다.
 */
export default function ChannelTalkEmbeddingFooterBar({
  channelCount,
  documentCount,
  allSelected,
  isSubmitting = false,
  onToggleAll,
  onEmbed,
}: ChannelTalkEmbeddingFooterBarProps) {
  return (
    <div className="border-line-normal-neutral flex flex-wrap items-center gap-x-1.5 gap-y-2 border-t px-8 py-3">
      <div className="flex min-w-0 flex-1 items-center">
        <button
          type="button"
          role="checkbox"
          aria-checked={allSelected}
          onClick={onToggleAll}
          className="flex min-w-0 cursor-pointer items-center gap-1.5"
        >
          <CheckboxIcon checked={allSelected} className="size-6" wrapperClassName="p-1.5" />
          <span className="text-body-small text-text-normal-alternative truncate">전체 선택하기</span>
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center gap-1.5">
          <p className="text-body-small text-text-normal-normal whitespace-nowrap">
            <span className="text-text-primary-assistive">{channelCount}</span>개 채널
          </p>
          <span aria-hidden="true" className="bg-dim-black-25 size-1 shrink-0 rounded-full" />
          <p className="text-body-small text-text-normal-normal whitespace-nowrap">
            <span className="text-text-primary-assistive">{documentCount}</span>개 도큐먼트
          </p>
        </div>

        {/* 채널 대화 자체도 독립 임베딩 대상이다 — 도큐먼트 없이 채널만 선택해도 제출 가능 */}
        <Button
          variant="box-solid-primary"
          size="md"
          onClick={onEmbed}
          disabled={isSubmitting || (channelCount === 0 && documentCount === 0)}
        >
          임베딩하기
        </Button>
      </div>
    </div>
  );
}
