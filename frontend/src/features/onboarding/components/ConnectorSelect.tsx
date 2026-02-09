'use client';

import { useState } from 'react';
import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import UnfoldMore from '@/public/icons/icon/unfold_more.svg';
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/shared/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import type { ConnectorAccount } from '../types/onboarding';

interface ConnectorSelectProps {
  label: string;
  placeholder: string;
  accounts: ConnectorAccount[];
  value: string;
  onChange: (v: string) => void;
}

export function ConnectorSelect({
  label,
  placeholder,
  accounts,
  value,
  onChange,
}: ConnectorSelectProps) {
  const [open, setOpen] = useState(false);

  const selected = accounts.find((a) => a.id === value);

  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1 text-heading-medium tracking-tight text-gray-80">
        <span className="size-[5px] rounded-full bg-red-50" />
        {label}
      </label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              'flex w-full items-center border bg-white tracking-tight cursor-pointer',
              selected
                ? 'gap-4 rounded-[10px] border-neutral-3 px-3 py-2.5'
                : 'h-[46px] justify-between rounded-lg border-neutral-4 px-2.5 py-1.5 text-body-small',
              open && 'bg-neutral-3',
            )}
          >
            {selected ? (
              <>
                {selected.picture ? (
                  <Image
                    src={selected.picture}
                    alt="프로필"
                    width={40}
                    height={40}
                    className="size-10 shrink-0 rounded-full border border-neutral-1"
                  />
                ) : (
                  <DefaultProfile className="size-10 shrink-0 rounded-full border border-neutral-1 text-gray-30" />
                )}
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-2.5">
                    <span className="max-w-[133px] truncate text-heading-small tracking-tight text-gray-80">
                      {selected.name}
                    </span>
                    <span className="shrink-0 rounded-md2 bg-neutral-2 px-1.5 py-0.5 text-body-xsmall text-gray-50">
                      {selected.id}
                    </span>
                  </div>
                  <span className="text-left truncate text-body-xsmall tracking-tight text-gray-50">
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
          className="rounded-lg border-neutral-5 p-0"
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
                  className="gap-3 rounded-none border-b border-neutral-2 px-3 py-2"
                >
                  {account.picture ? (
                    <Image
                      src={account.picture}
                      alt=""
                      width={40}
                      height={40}
                      className="size-10 shrink-0 rounded-full border border-neutral-1"
                    />
                  ) : (
                    <DefaultProfile className="size-10 shrink-0 rounded-full border border-neutral-1 text-gray-30" />
                  )}
                  <div className="flex min-w-0 flex-col items-start gap-0.5">
                    <div className="flex items-center gap-2.5">
                      <span className="max-w-[175px] truncate text-heading-small tracking-tight text-gray-80">
                        {account.name}
                      </span>
                      <span className="rounded-md2 bg-neutral-2 px-1.5 py-0.5 text-body-xsmall text-gray-50">
                        {account.id}
                      </span>
                    </div>
                    <span className="truncate text-label-xsmall tracking-tight text-gray-50">
                      {account.email}
                    </span>
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
