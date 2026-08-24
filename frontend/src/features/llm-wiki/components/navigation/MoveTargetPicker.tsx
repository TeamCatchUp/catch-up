'use client';

import { useMemo, useState } from 'react';

import IconCaretDown from '@/public/icons/icon/arrow_dropdown_down.svg';
import IconCaretRight from '@/public/icons/icon/arrow_right_filled.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconSearch from '@/public/icons/icon/search_300.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { cn } from '@/shared/utils/cn';

export interface MoveTargetFolder {
  id: string;
  label: string;
}

export interface MoveTargetChannel {
  id: string;
  label: string;
  folders: readonly MoveTargetFolder[];
}

/** 고른 자리. folderId가 null이면 채널 바로 아래다 */
export interface MoveTarget {
  channelId: string;
  folderId: string | null;
  label: string;
}

export interface MoveTargetPickerProps {
  channels?: readonly MoveTargetChannel[];
  onSelect?: (target: MoveTarget) => void;
  className?: string;
}

const SEARCH_PLACEHOLDER = '파일 옮길 곳 선택';

const NO_CHANNELS: readonly MoveTargetChannel[] = [];

const matches = (label: string, keyword: string) => label.toLowerCase().includes(keyword.toLowerCase());

/** 행 하나의 공통 뼈대. 채널·폴더가 들여쓰기와 앞 슬롯만 다르다 */
function TargetRow({
  label,
  depth,
  leading,
  onSelect,
}: {
  label: string;
  depth: 0 | 1;
  leading: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <div
      data-testid="move-target-row"
      className={cn(
        'hover:bg-fill-normal-interaction-hover flex h-9 items-center gap-3 rounded-lg py-1.5 pr-2.5 transition-colors',
        depth === 0 ? 'pl-2.5' : 'pl-5',
      )}
    >
      {leading}
      <button type="button" onClick={onSelect} className="flex min-w-0 flex-1 cursor-pointer">
        <span className="text-body-small text-text-normal-normal min-w-0 truncate text-left">{label}</span>
      </button>
    </div>
  );
}

/**
 * 문서를 옮길 채널·폴더를 고르는 패널. 대상 목록은 소비처가 넘기고,
 * 이 컴포넌트는 검색·접기와 고른 자리를 알리는 일만 한다.
 */
export default function MoveTargetPicker({ channels = NO_CHANNELS, onSelect, className }: MoveTargetPickerProps) {
  const [keyword, setKeyword] = useState('');
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(() => new Set());

  const searching = keyword.trim().length > 0;

  // 채널명이 걸리면 그 채널의 폴더를 모두 남기고, 폴더만 걸리면 걸린 폴더만 남긴다
  const visible = useMemo(() => {
    if (!searching) return channels;
    const term = keyword.trim();
    return channels
      .map((channel) => ({
        ...channel,
        folders: matches(channel.label, term)
          ? channel.folders
          : channel.folders.filter((folder) => matches(folder.label, term)),
      }))
      .filter((channel) => matches(channel.label, term) || channel.folders.length > 0);
  }, [channels, keyword, searching]);

  const toggle = (channelId: string) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (!next.delete(channelId)) next.add(channelId);
      return next;
    });

  return (
    <div
      data-testid="move-target-picker"
      className={cn(
        'bg-background-elevated-normal border-line-normal-normal shadow-modal flex h-95 w-75 flex-col gap-3 rounded-xl border py-2.5',
        className,
      )}
    >
      {/* 공용 Input에는 아이콘 슬롯이 없어 같은 토큰으로 직접 조립한다 */}
      <div className="px-2.5">
        <div className="border-line-normal-neutral focus-within:border-line-primary-normal flex h-9 items-center gap-2 rounded-lg border px-2.5 py-1.5">
          <IconSearch aria-hidden className="text-icon-normal-alternative size-5 shrink-0" />
          <input
            type="text"
            value={keyword}
            placeholder={SEARCH_PLACEHOLDER}
            aria-label={SEARCH_PLACEHOLDER}
            onChange={(event) => setKeyword(event.target.value)}
            className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive min-w-0 flex-1 bg-transparent outline-none"
          />
        </div>
      </div>

      {/* 빈 목록·검색 결과 없음 문구는 시안이 없어 만들지 않는다 */}
      <ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-1.5">
        {visible.map((channel) => {
          // 검색 중에는 걸린 폴더가 보여야 하므로 접힌 채널도 펼친다
          const expanded = searching || expandedIds.has(channel.id);

          return (
            <li key={channel.id} className="flex flex-col gap-0.5">
              <TargetRow
                label={channel.label}
                depth={0}
                onSelect={() => onSelect?.({ channelId: channel.id, folderId: null, label: channel.label })}
                leading={
                  <>
                    <span className="flex size-5.5 shrink-0 items-center justify-center">
                      {channel.folders.length > 0 && (
                        <button
                          type="button"
                          aria-label={`${channel.label} ${expanded ? '접기' : '펼치기'}`}
                          aria-expanded={expanded}
                          onClick={() => toggle(channel.id)}
                          className="hover:bg-fill-normal-interaction-pressed text-icon-normal-neutral flex size-5.5 cursor-pointer items-center justify-center rounded-full"
                        >
                          {expanded ? (
                            <IconCaretDown aria-hidden className="size-4.5" />
                          ) : (
                            <IconCaretRight aria-hidden className="size-4.5" />
                          )}
                        </button>
                      )}
                    </span>
                    <span className="flex size-5.5 shrink-0 items-center justify-center">
                      <IconWikiChannel aria-hidden className="text-icon-normal-neutral size-5" />
                    </span>
                  </>
                }
              />

              {expanded &&
                channel.folders.map((folder) => (
                  <TargetRow
                    key={folder.id}
                    label={folder.label}
                    depth={1}
                    onSelect={() => onSelect?.({ channelId: channel.id, folderId: folder.id, label: folder.label })}
                    leading={
                      <>
                        <span className="flex size-5.5 shrink-0 items-center justify-center">
                          <span
                            aria-hidden
                            className="border-icon-normal-assistive size-1.5 rounded-full border-[1.5px]"
                          />
                        </span>
                        <span className="flex size-5.5 shrink-0 items-center justify-center">
                          <IconFolder aria-hidden className="text-icon-normal-neutral size-5" />
                        </span>
                      </>
                    }
                  />
                ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
