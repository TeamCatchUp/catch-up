import type { ComponentType, SVGProps } from 'react';

import IconBook from '@/public/icons/icon/book.svg';
import IconTagChannel from '@/public/icons/icon/tag_channel.svg';

const ICONS: Record<ChannelTalkNameIconKind, ComponentType<SVGProps<SVGSVGElement>>> = {
  channel: IconTagChannel,
  document: IconBook,
};

export type ChannelTalkNameIconKind = 'channel' | 'document';

interface ChannelTalkNameIconProps {
  kind: ChannelTalkNameIconKind;
}

/**
 * 채널·도큐먼트 이름 앞에 붙는 20×20 아이콘 칩.
 * Figma `17414:98000` — `fill/normal/strong` 배경 + `line/normal/normal` 테두리,
 * padding 2, radius 6, 안쪽 아이콘 16. 좌 패널·채널 헤더·도큐먼트 행 셋 다 같다.
 */
export default function ChannelTalkNameIcon({ kind }: ChannelTalkNameIconProps) {
  const Icon = ICONS[kind];

  return (
    <span
      aria-hidden="true"
      className="bg-fill-normal-strong border-line-normal-normal rounded-md2 flex shrink-0 items-center border p-0.5"
    >
      <Icon className="text-icon-normal-neutral size-4 shrink-0" />
    </span>
  );
}
