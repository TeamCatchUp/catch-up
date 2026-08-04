'use client';

import IconBook from '@/public/icons/icon/book.svg';
import IconReply from '@/public/icons/icon/reply.svg';
import CheckboxIcon from '@/shared/components/ui/checkbox-icon';

import type { Period } from '../../../../constants/period';
import EntityChip from '../EntityChip';
import PeriodSelect from '../PeriodSelect';
import type { ChannelTalkDocumentTarget } from './channelTalkEmbeddingTarget';

interface ChannelTalkDocumentItemProps {
  document: ChannelTalkDocumentTarget;
  selected: boolean;
  onToggle: () => void;
  onDataRangeChange: (next: Period) => void;
}

/**
 * 채널 하위 도큐먼트 스페이스 한 줄.
 * Figma `17449:111885` 404×56 — 체크박스 36 + gap 10 + 본문(fill).
 *
 * 구분선은 행 전체가 아니라 **본문에만** 붙는다. 체크박스 왼쪽은 선이 없어서
 * 계층이 들여쓰기로 읽힌다.
 * `icon/reply`는 180도 회전해서 위에서 내려오는 가지처럼 쓴다.
 */
export default function ChannelTalkDocumentItem({
  document,
  selected,
  onToggle,
  onDataRangeChange,
}: ChannelTalkDocumentItemProps) {
  return (
    <li className="flex items-center gap-2.5">
      <button
        type="button"
        role="checkbox"
        aria-checked={selected}
        aria-label={document.name}
        onClick={onToggle}
        className="shrink-0 cursor-pointer"
      >
        <CheckboxIcon checked={selected} className="size-6" wrapperClassName="p-1.5" />
      </button>

      <div className="border-line-normal-assistive flex min-w-0 flex-1 items-center gap-8 border-b py-2.5">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <IconReply aria-hidden="true" className="text-icon-normal-alternative size-6 shrink-0" />
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <EntityChip icon={IconBook} />
            <span className="text-body-small text-text-normal-neutral min-w-0 flex-1 truncate">{document.name}</span>
          </div>
        </div>

        {/* Figma Dropdown h36·w68 — 폭을 80(min-w-20)으로 올린 근거는 ChannelTalkChannelGroup 주석 참조 */}
        <PeriodSelect value={document.dataRange} onChange={onDataRangeChange} className="h-9 min-w-20 shrink-0" />
      </div>
    </li>
  );
}
