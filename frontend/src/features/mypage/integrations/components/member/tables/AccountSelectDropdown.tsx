'use client';

import { useState } from 'react';
import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconUnfoldMore from '@/public/icons/icon/unfold_more.svg';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { Switch } from '@/shared/components/ui/switch';
import { cn } from '@/shared/utils/cn';

/** 드롭다운에 표시할 계정 후보 */
export interface AccountOption {
  id: string;
  name: string;
  identifier: string;
  picture?: string | null;
}

interface AccountSelectDropdownProps {
  /** 현재 상태: '미사용' | '미등록' */
  status: '미사용' | '미등록';
  /** 선택 가능한 계정 목록 */
  options: AccountOption[];
  /** 수정 모드에서 선택된 계정 (override) */
  selectedAccount?: AccountOption;
  /** 계정 선택 시 콜백 */
  onSelect: (account: AccountOption) => void;
  /** "미사용" 토글 변경 시 콜백 */
  onToggleUnused: (unused: boolean) => void;
}

const AccountSelectDropdown = ({
  status,
  options,
  selectedAccount,
  onSelect,
  onToggleUnused,
}: AccountSelectDropdownProps) => {
  const [open, setOpen] = useState(false);
  const [localUnused, setLocalUnused] = useState(status === '미사용');
  const isUnused = !selectedAccount && localUnused;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            'border-edge-neutral hover:bg-fill-strong bg-fill-normal flex h-9 w-full min-w-0 cursor-pointer items-center justify-between rounded-lg border px-2.5 py-1.5',
            open && 'bg-fill-interaction-pressed',
          )}
        >
          {selectedAccount ? (
            <div className="flex min-w-0 items-center gap-2">
              {selectedAccount.picture ? (
                <Image
                  src={selectedAccount.picture}
                  alt=""
                  width={20}
                  height={20}
                  className="size-5 shrink-0 rounded-full"
                />
              ) : (
                <DefaultProfile className="text-content-assistive size-5 shrink-0 rounded-full" />
              )}
              <span className="text-body-small text-content-strong truncate">{selectedAccount.name}</span>
            </div>
          ) : (
            <span
              className={cn('text-body-small truncate', isUnused ? 'text-content-strong' : 'text-content-assistive')}
            >
              {isUnused ? '해당 협업 툴 미사용' : '계정 선택하기'}
            </span>
          )}
          <IconUnfoldMore className="size-6 shrink-0" />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="start"
        sideOffset={2}
        className="shadow-dropdown-menu border-edge-normal w-71 overflow-clip rounded-xl p-0 py-2.5"
      >
        <Command shouldFilter>
          {/* 검색바 */}
          <div className="px-2.5">
            <CommandInput placeholder="이름, 이메일, 아이디를 검색하세요." />
          </div>

          {/* 미사용 토글 */}
          <div className="px-2.5 py-2">
            <div className="border-edge-assistive flex items-center gap-2 rounded-lg border bg-[#fffafa] px-2.5 py-2">
              <span className="text-body-small text-content-alternative flex-1">해당 협업 툴을 사용하지 않습니다.</span>
              <Switch
                checked={isUnused}
                onCheckedChange={(checked) => {
                  setLocalUnused(checked);
                  onToggleUnused(checked);
                }}
              />
            </div>
          </div>

          {/* 계정 목록 */}
          <CommandList className="max-h-70 px-0 py-0">
            <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
            {options.map((account) => (
              <CommandItem
                key={`${account.name}-${account.identifier}`}
                value={`${account.name} ${account.identifier}`}
                onSelect={() => {
                  onSelect(account);
                  setOpen(false);
                }}
                className="border-edge-assistive gap-3 rounded-none border-b px-3 py-2"
              >
                {account.picture ? (
                  <Image
                    src={account.picture}
                    alt=""
                    width={40}
                    height={40}
                    className="size-10 shrink-0 rounded-full"
                  />
                ) : (
                  <DefaultProfile className="text-content-assistive size-10 shrink-0 rounded-full" />
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-heading-small text-content-normal max-w-43.75 truncate">{account.name}</span>
                  <span className="text-label-xsmall text-content-alternative truncate">{account.identifier}</span>
                </div>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

export default AccountSelectDropdown;
