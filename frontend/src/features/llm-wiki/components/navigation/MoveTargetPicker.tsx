'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import IconAdd from '@/public/icons/icon/add.svg';
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
  /** 새 폴더 만들기. 권한이 없으면 넘기지 않고, 그러면 하단 진입점도 없다 */
  onCreateFolder?: (name: string) => void;
  className?: string;
}

const SEARCH_PLACEHOLDER = '파일 옮길 곳 선택';

const matches = (label: string, keyword: string) => label.toLowerCase().includes(keyword.toLowerCase());

/** 행 하나의 공통 뼈대. 채널·폴더는 앞 슬롯만 다르고 들여쓰기는 그 슬롯이 만든다. 현재 위치는 잠긴다 */
function TargetRow({
  label,
  leading,
  disabled = false,
  onSelect,
}: {
  label: string;
  leading: React.ReactNode;
  disabled?: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      data-testid="move-target-row"
      className={cn(
        'relative flex h-9 items-center gap-3 rounded-lg px-2.5 py-1.5 transition-colors',
        !disabled && 'hover:bg-fill-normal-interaction-hover',
      )}
    >
      {/* 행 전체 클릭 — 캐럿 버튼과의 중첩을 피해 오버레이로 분리한다 */}
      <button
        type="button"
        aria-label={label}
        disabled={disabled}
        onClick={onSelect}
        className={cn('absolute inset-0 rounded-lg', disabled ? 'cursor-default' : 'cursor-pointer')}
      />
      {leading}
      <span
        className={cn(
          'text-body-small min-w-0 flex-1 truncate text-left',
          disabled ? 'text-text-normal-assistive' : 'text-text-normal-normal',
        )}
      >
        {label}
      </span>
    </div>
  );
}

/** 하단 "새 폴더" 진입점. 누르면 같은 자리에서 이름 입력으로 바뀐다 */
function FolderCreateFooter({ onCreate }: { onCreate: (name: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const close = () => {
    setEditing(false);
    setName('');
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      // 패널 팝오버까지 닫히지 않게 여기서 끊는다
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    // 조합 중 Enter는 한글 확정이라 제출로 세지 않는다
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault();
      const trimmed = name.trim();
      if (!trimmed) return;
      onCreate(trimmed);
      close();
    }
  };

  return (
    <div className="border-line-normal-neutral border-t">
      {editing ? (
        <div className="p-1.5">
          <div className="border-line-normal-neutral focus-within:border-line-primary-normal flex h-9 items-center gap-2 rounded-lg border px-2.5 py-1.5">
            <IconFolder aria-hidden className="text-icon-normal-alternative size-5 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={name}
              placeholder="폴더 이름"
              aria-label="폴더 이름"
              onChange={(event) => setName(event.target.value)}
              onKeyDown={handleKeyDown}
              className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive min-w-0 flex-1 bg-transparent outline-none"
            />
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="hover:bg-fill-normal-interaction-hover flex w-full cursor-pointer items-center gap-3 p-2.5 text-left transition-colors"
        >
          <span className="flex size-5.5 shrink-0 items-center justify-center">
            <IconAdd aria-hidden className="text-icon-normal-neutral size-5" />
          </span>
          <span className="text-body-small text-text-normal-alternative">새 폴더</span>
        </button>
      )}
    </div>
  );
}

/**
 * 문서를 옮길 자리를 고르는 패널. 대상은 그 문서의 채널 하나이고,
 * 채널 행을 고르면 채널 루트(folderId null)로 꺼낸다.
 */
export default function MoveTargetPicker({
  channel,
  currentFolderId,
  onSelect,
  onCreateFolder,
  className,
}: MoveTargetPickerProps) {
  const [keyword, setKeyword] = useState('');
  // 열릴 때는 항상 전체 펼침 — 폴더가 바로 보여야 한다(사용자 확정)
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
        'bg-background-elevated-normal border-line-normal-normal shadow-modal flex max-h-95 w-75 flex-col gap-3 rounded-xl border pt-2.5',
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
                        className="hover:bg-fill-normal-interaction-pressed text-icon-normal-neutral relative flex size-5.5 cursor-pointer items-center justify-center rounded-full"
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

      {channel && onCreateFolder && <FolderCreateFooter onCreate={onCreateFolder} />}
    </div>
  );
}
