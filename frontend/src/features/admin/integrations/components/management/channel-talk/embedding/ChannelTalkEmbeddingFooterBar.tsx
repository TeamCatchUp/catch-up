'use client';

import { Button } from '@/shared/components/ui/button';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

interface ChannelTalkEmbeddingFooterBarProps {
  channelCount: number;
  documentCount: number;
  allSelected: boolean;
  partiallySelected: boolean;
  onToggleAll: () => void;
  onEmbed: () => void;
}

/**
 * 임베딩 대상 선택 단계의 하단 바.
 * Figma `17414:97736` 780×60 — 위선만 있고 배경은 없다. px 32 / py 12.
 *
 * 스텝 ①의 {@link ChannelTalkFooterBar}(`17345:84633`)와 다른 물건이다 —
 * 저건 `채널 추가` + `임베딩하기` 두 버튼이고 이건 전체 선택 체크박스 + 버튼 하나다.
 *
 * 집계는 숫자만 `#3385FF`로 강조된다. 그 값을 주는 `bg-*`가 없어 텍스트 토큰
 * `text-primary-assistive`를 쓴다 — 스텝 ① 하단 바와 같은 처리다.
 */
export default function ChannelTalkEmbeddingFooterBar({
  channelCount,
  documentCount,
  allSelected,
  partiallySelected,
  onToggleAll,
  onEmbed,
}: ChannelTalkEmbeddingFooterBarProps) {
  return (
    <div className="border-line-normal-neutral flex flex-wrap items-center gap-x-1.5 gap-y-2 border-t px-8 py-3">
      <div className="flex min-w-0 flex-1 items-center gap-1.5">
        <button
          type="button"
          role="checkbox"
          aria-checked={partiallySelected ? 'mixed' : allSelected}
          aria-label="전체 선택하기"
          onClick={onToggleAll}
          className="shrink-0 cursor-pointer"
        >
          <CheckboxIcon
            checked={allSelected}
            indeterminate={partiallySelected}
            className="size-6"
            wrapperClassName="p-1.5"
          />
        </button>
        <span className="text-body-small text-text-normal-alternative truncate">전체 선택하기</span>
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

        <Button variant="box-solid-primary" size="md" onClick={onEmbed} disabled={documentCount === 0}>
          임베딩하기
        </Button>
      </div>
    </div>
  );
}
