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
  /** 대상 채널 하나. 이동 API가 같은 채널 안만 받아 목록을 채널 단위로 좁힌다 */
  channel?: MoveTargetChannel;
  /** 문서가 지금 있는 자리. null이면 채널 행을, 폴더 id면 그 폴더 행을 비활성한다 */
  currentFolderId?: string | null;
  onSelect?: (target: MoveTarget) => void;
  className?: string;
}

const SEARCH_PLACEHOLDER = '파일 옮길 곳 선택';

const matches = (label: string, keyword: string) => label.toLowerCase().includes(keyword.toLowerCase());

/** 행 하나의 공통 뼈대. 채널·폴더가 들여쓰기와 앞 슬롯만 다르고, 현재 위치는 잠긴다 */
function TargetRow({
  label,
  depth,
  leading,
  disabled = false,
  onSelect,
}: {
  label: string;
  depth: 0 | 1;
  leading: React.ReactNode;
  disabled?: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      data-testid="move-target-row"
      className={cn(
        'flex h-9 items-center gap-3 rounded-lg py-1.5 pr-2.5 transition-colors',
        depth === 0 ? 'pl-2.5' : 'pl-5',
        !disabled && 'hover:bg-fill-normal-interaction-hover',
      )}
    >
      {leading}
      <button
        type="button"
        disabled={disabled}
        onClick={onSelect}
        className={cn('flex min-w-0 flex-1', disabled ? 'cursor-default' : 'cursor-pointer')}
      >
        <span
          className={cn(
            'text-body-small min-w-0 truncate text-left',
            disabled ? 'text-text-normal-assistive' : 'text-text-normal-normal',
          )}
        >
          {label}
        </span>
      </button>
    </div>
  );
}

/**
 * 문서를 옮길 자리를 고르는 패널. 대상은 그 문서의 채널 하나이고,
 * 채널 행을 고르면 채널 루트(folderId null)로 꺼낸다.
 */
export default function MoveTargetPicker({ channel, currentFolderId, onSelect, className }: MoveTargetPickerProps) {
  const [keyword, setKeyword] = useState('');
  // 채널이 하나뿐이라 처음부터 펼쳐 폴더가 바로 보이게 둔다
  const [collapsed, setCollapsed] = useState(false);

  const searching = keyword.trim().length > 0;

  // 채널명이 걸리면 폴더를 모두 남기고, 폴더만 걸리면 걸린 폴더만 남긴다
  const visible = useMemo(() => {
    if (!channel || !searching) return channel;
    const term = keyword.trim();
    const folders = matches(channel.label, term)
      ? channel.folders
      : channel.folders.filter((folder) => matches(folder.label, term));
    if (!matches(channel.label, term) && folders.length === 0) return undefined;
    return { ...channel, folders };
  }, [channel, keyword, searching]);

  // 검색 중에는 걸린 폴더가 보여야 하므로 접혀 있어도 펼친다
  const expanded = searching || !collapsed;

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
        {visible && (
          <li className="flex flex-col gap-0.5">
            <TargetRow
              label={visible.label}
              depth={0}
              disabled={currentFolderId === null}
              onSelect={() => onSelect?.({ channelId: visible.id, folderId: null, label: visible.label })}
              leading={
                <>
                  <span className="flex size-5.5 shrink-0 items-center justify-center">
                    {visible.folders.length > 0 && (
                      <button
                        type="button"
                        aria-label={`${visible.label} ${expanded ? '접기' : '펼치기'}`}
                        aria-expanded={expanded}
                        onClick={() => setCollapsed((prev) => !prev)}
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
              visible.folders.map((folder) => (
                <TargetRow
                  key={folder.id}
                  label={folder.label}
                  depth={1}
                  disabled={folder.id === currentFolderId}
                  onSelect={() => onSelect?.({ channelId: visible.id, folderId: folder.id, label: folder.label })}
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
        )}
      </ul>
    </div>
  );
}
