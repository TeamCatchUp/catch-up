'use client';

import { useState } from 'react';

import IconEditSquare from '@/public/icons/icon/edit_square.svg';
import IconKebabHorizontal from '@/public/icons/icon/kebab_horizontal.svg';
import IconLink from '@/public/icons/icon/link.svg';
import SnbDropdownMenu from '@/shared/components/layout/sideNavBar/SnbDropdownMenu';
import SnbRenamePopover from '@/shared/components/layout/sideNavBar/SnbRenamePopover';
import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';

/** 버튼 규격은 헤더 variant에 묶인다 — main과 detail이 크기·모서리를 가른다. */
const ACTION_SPEC = {
  main: { size: 'md', box: undefined, icon: 'size-6' },
  detail: { size: 'sm', box: 'size-7', icon: 'size-5' },
} as const;

// 껍데기는 메뉴·이름 입력이 직접 그린다. overflow-visible이 없으면 그림자가 잘린다
const POPOVER_SHELL_CLASS = 'overflow-visible border-0 bg-transparent p-0 shadow-none';

export interface WikiHeaderActionsProps {
  /** 헤더 variant와 같은 값을 받는다 — 버튼 크기·모서리가 여기서 갈린다 */
  variant: 'main' | 'detail';
  /** 이름 바꾸기 입력의 아이콘을 가른다 */
  kind: 'channel' | 'folder';
  /** 이름 바꾸기 입력의 초기값 */
  name: string;
  onCopyLink: () => void;
  /** 없으면 이름 바꾸기 항목이 빠지고, 남는 항목이 없어 케밥 자체가 서지 않는다 */
  onRenameSubmit?: (name: string) => void;
}

/**
 * 채널·폴더 헤더 우측 액션 — 링크 복사 + 케밥 메뉴.
 * 시안의 채널 설정 보기·도움말·버전 기록과 하단 메타는 목적지·데이터가 없어 넣지 않는다.
 */
export default function WikiHeaderActions({ variant, kind, name, onCopyLink, onRenameSubmit }: WikiHeaderActionsProps) {
  const spec = ACTION_SPEC[variant];
  // 케밥에서 이름 입력으로 이어 열린다 — 같은 팝오버 자리에서 내용만 갈린다
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);

  const close = () => {
    setOpen(false);
    setRenaming(false);
  };

  return (
    <>
      <Button
        variant="icon-only-gray"
        size={spec.size}
        className={spec.box}
        aria-label="링크 복사"
        onClick={onCopyLink}
      >
        <IconLink aria-hidden className={spec.icon} />
      </Button>

      {onRenameSubmit && (
        <Popover open={open} onOpenChange={(next) => (next ? setOpen(true) : close())}>
          <PopoverTrigger asChild>
            <Button variant="icon-only-gray" size={spec.size} className={spec.box} aria-label="작업 더보기">
              <IconKebabHorizontal aria-hidden className={spec.icon} />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="end"
            className={POPOVER_SHELL_CLASS}
            onCloseAutoFocus={(event) => event.preventDefault()}
          >
            {renaming ? (
              <SnbRenamePopover
                kind={kind}
                defaultValue={name}
                onSubmit={(next) => {
                  onRenameSubmit(next);
                  close();
                }}
                onCancel={close}
              />
            ) : (
              <SnbDropdownMenu
                categoryLabel="작업 더보기"
                groups={[
                  [{ id: 'rename', label: '이름 바꾸기', Icon: IconEditSquare, onSelect: () => setRenaming(true) }],
                ]}
              />
            )}
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}
