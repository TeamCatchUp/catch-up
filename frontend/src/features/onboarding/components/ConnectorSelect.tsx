'use client';

import { useState } from 'react';
import Image from 'next/image';

import CheckboxChecked from '@/public/icons/icon/checkbox_checked.svg';
import CheckboxUnchecked from '@/public/icons/icon/checkbox_unchecked.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import UnfoldMore from '@/public/icons/icon/unfold_more.svg';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import type { ConnectorAccount } from '../types/onboarding';

interface ConnectorSelectProps {
  label: string;
  placeholder: string;
  accounts: ConnectorAccount[];
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  onDisabledChange?: (disabled: boolean) => void;
}

export function ConnectorSelect({
  label,
  placeholder,
  accounts,
  value,
  onChange,
  disabled = false,
  onDisabledChange,
}: ConnectorSelectProps) {
  const [open, setOpen] = useState(false);

  const selected = !disabled ? accounts.find((a) => a.id === value) : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-heading-medium text-gray-80 flex items-center gap-1 tracking-tight">
          <span className="size-[5px] rounded-full bg-red-50" />
          {label}
        </label>
        {onDisabledChange && (
          <button
            type="button"
            className="flex cursor-pointer items-center gap-0.5"
            onClick={() => {
              const next = !disabled;
              onDisabledChange(next);
              if (next) onChange('');
            }}
          >
            <span className="text-body-xsmall text-gray-80 tracking-tight">현재 사용하지 않는 툴이에요</span>
            <div className="p-1">
              {disabled ? <CheckboxChecked className="size-5" /> : <CheckboxUnchecked className="size-5" />}
            </div>
          </button>
        )}
      </div>
      <Popover open={disabled ? false : open} onOpenChange={disabled ? undefined : setOpen}>
        <PopoverTrigger asChild disabled={disabled}>
          <button
            type="button"
            disabled={disabled}
            className={cn(
              'flex w-full items-center border bg-white tracking-tight',
              disabled
                ? 'border-neutral-4 text-body-small h-[46px] cursor-not-allowed justify-between rounded-lg px-2.5 py-1.5'
                : 'cursor-pointer',
              !disabled &&
                (selected
                  ? 'border-neutral-3 gap-4 rounded-[10px] px-3 py-2.5'
                  : 'border-neutral-4 text-body-small h-[46px] justify-between rounded-lg px-2.5 py-1.5'),
              !disabled && open && 'bg-neutral-3',
            )}
          >
            {disabled ? (
              <>
                <span className="text-gray-30">사용하지 않는 도구로 설정되어 있습니다</span>
                <UnfoldMore className="size-5 shrink-0 text-gray-30" />
              </>
            ) : selected ? (
              <>
                {selected.picture ? (
                  <Image
                    src={selected.picture}
                    alt="프로필"
                    width={40}
                    height={40}
                    className="border-neutral-1 size-10 shrink-0 rounded-full border"
                  />
                ) : (
                  <DefaultProfile className="border-neutral-1 text-gray-30 size-10 shrink-0 rounded-full border" />
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-2.5">
                    <span className="text-heading-small text-gray-80 max-w-[133px] truncate tracking-tight">
                      {selected.name}
                    </span>
                    <span className="rounded-md2 bg-neutral-2 text-body-xsmall shrink-0 px-1.5 py-0.5 text-gray-50">
                      {selected.id}
                    </span>
                  </div>
                  <span className="text-body-xsmall truncate text-left tracking-tight text-gray-50">
                    {selected.email}
                  </span>
                </div>
                <UnfoldMore className="size-6 shrink-0 text-gray-50" />
              </>
            ) : (
              <>
                <span className="text-gray-30">{placeholder}</span>
                <UnfoldMore className="size-5 shrink-0 text-gray-50" />
              </>
            )}
          </button>
        </PopoverTrigger>
        <PopoverContent
          className="border-neutral-5 rounded-lg p-0"
          style={{ width: 'var(--radix-popover-trigger-width)' }}
          align="start"
        >
          <Command className="max-h-[260px] gap-2.5 rounded-lg py-2.5">
            <div className="px-2.5">
              <CommandInput placeholder="이름, 이메일, 아이디를 검색하세요." />
            </div>
            <CommandList className="max-h-none px-0 py-0">
              <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
              {accounts.map((account) => (
                <CommandItem
                  key={account.id}
                  value={`${account.name} ${account.email} ${account.id}`}
                  onSelect={() => {
                    onChange(account.id);
                    setOpen(false);
                  }}
                  className="border-neutral-2 gap-3 rounded-none border-b px-3 py-2"
                >
                  {account.picture ? (
                    <Image
                      src={account.picture}
                      alt=""
                      width={40}
                      height={40}
                      className="border-neutral-1 size-10 shrink-0 rounded-full border"
                    />
                  ) : (
                    <DefaultProfile className="border-neutral-1 text-gray-30 size-10 shrink-0 rounded-full border" />
                  )}
                  <div className="flex min-w-0 flex-col items-start gap-0.5">
                    <div className="flex items-center gap-2.5">
                      <span className="text-heading-small text-gray-80 max-w-[175px] truncate tracking-tight">
                        {account.name}
                      </span>
                      <span className="rounded-md2 bg-neutral-2 text-body-xsmall px-1.5 py-0.5 text-gray-50">
                        {account.id}
                      </span>
                    </div>
                    <span className="text-label-xsmall truncate tracking-tight text-gray-50">{account.email}</span>
                  </div>
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
