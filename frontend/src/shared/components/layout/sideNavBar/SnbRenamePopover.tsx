'use client';

import { useEffect, useRef, useState } from 'react';

import IconFile from '@/public/icons/icon/file.svg';
import IconFolder from '@/public/icons/icon/folder.svg';
import IconWikiChannel from '@/public/icons/icon/wiki_channel.svg';
import { cn } from '@/shared/utils/cn';

export type SnbRenameKind = 'channel' | 'folder' | 'document';

const KIND_ICON: Record<SnbRenameKind, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  channel: IconWikiChannel,
  folder: IconFolder,
  document: IconFile,
};

// 입력 영역이 자라다 멈추는 지점. 넘으면 스크롤로 넘긴다
const MAX_TEXTAREA_HEIGHT_PX = 200;

export interface SnbRenamePopoverProps {
  /** 아이콘만 가른다 — 셸·입력 규격은 3종이 같다 */
  kind: SnbRenameKind;
  /** 편집 시작 시점의 이름. 열릴 때 전체 선택된다 */
  defaultValue?: string;
  placeholder?: string;
  /** Enter. 값을 다듬지 않고 그대로 넘긴다 — 검증 규칙이 정해지지 않았다 */
  onSubmit?: (name: string) => void;
  /** Escape */
  onCancel?: () => void;
  'aria-label'?: string;
  className?: string;
}

/**
 * SNB 트리 행 위에 뜨는 이름 바꾸기 입력. 팝오버 배치·열고 닫기는 소비처가 들고,
 * 이 컴포넌트는 입력과 키 처리만 맡는다.
 */
export default function SnbRenamePopover({
  kind,
  defaultValue = '',
  placeholder,
  onSubmit,
  onCancel,
  'aria-label': ariaLabel = '이름 바꾸기',
  className,
}: SnbRenamePopoverProps) {
  const Icon = KIND_ICON[kind];
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState(defaultValue);

  // 열리면 바로 편집 상태. 기존 이름은 전체 선택해 덮어쓰기 쉽게 둔다
  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.focus();
    element.setSelectionRange(0, element.value.length);
  }, []);

  // 내용만큼 자라다 상한에서 멈추고, 넘치면 스크롤로 넘긴다
  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = 'auto';
    const contentHeight = element.scrollHeight;
    element.style.height = `${Math.min(contentHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
    element.style.overflowY = contentHeight > MAX_TEXTAREA_HEIGHT_PX ? 'auto' : 'hidden';
  }, [value]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onCancel?.();
      return;
    }
    // 조합 중 Enter는 한글 확정이라 제출로 세지 않는다
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSubmit?.(value);
    }
  };

  return (
    <div
      data-testid="snb-rename-popover"
      className={cn(
        'bg-background-elevated-normal border-line-normal-normal shadow-dropdown-menu flex w-81.25 items-center gap-1.5 rounded-xl border p-1.5',
        className,
      )}
    >
      <span
        data-testid="snb-rename-popover-icon"
        className="bg-fill-primary-normal-assistive flex size-8.75 shrink-0 items-center justify-center rounded-lg"
      >
        <Icon aria-hidden className="text-icon-primary-assistive size-5" />
      </span>
      {/* 테두리를 ring으로 그린다 — border면 1px↔1.5px 전환마다 입력 폭이 밀린다 */}
      <div
        data-testid="snb-rename-popover-field"
        className="bg-fill-normal-normal ring-line-normal-neutral focus-within:ring-line-primary-normal flex min-w-0 flex-1 items-center rounded-lg px-2 py-1.5 ring-1 focus-within:ring-[1.5px]"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          placeholder={placeholder}
          aria-label={ariaLabel}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          className="text-body-small text-text-normal-normal placeholder:text-text-normal-assistive max-h-50 w-full resize-none overflow-hidden bg-transparent outline-none"
        />
      </div>
    </div>
  );
}
