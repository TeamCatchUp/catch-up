'use client';

import { useMemo, useRef, useState } from 'react';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import UnfoldMore from '@/public/icons/icon/unfold_more.svg';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import type { ConnectorAccount } from '../model/onboarding.types';

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
  const [search, setSearch] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = accounts.find((a) => a.id === value);

  const filtered = useMemo(() => {
    if (!search) return accounts;
    const q = search.toLowerCase();
    return accounts.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.email.toLowerCase().includes(q) ||
        a.tag.toLowerCase().includes(q),
    );
  }, [accounts, search]);

  const handleSelect = (id: string) => {
    onChange(id);
    setOpen(false);
    setSearch('');
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1 text-heading-medium tracking-tight text-gray-80">
        <span className="size-[5px] rounded-full bg-red-50" />
        {label}
      </label>
      <Popover
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) setSearch('');
        }}
      >
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
                  <img
                    src={selected.picture}
                    alt=""
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
                      {selected.tag}
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
          className="flex max-h-[260px] flex-col rounded-lg border-neutral-5 px-0 py-2.5"
          style={{ width: 'var(--radix-popover-trigger-width)' }}
          align="start"
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            inputRef.current?.focus();
          }}
        >
          {/* 검색 */}
          <div className="shrink-0 px-2.5 pb-2">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="이름, 이메일, 아이디를 검색하세요."
              className="min-h-[40px] w-full rounded-lg border border-transparent bg-neutral-1 px-3 py-2 text-body-small tracking-tight text-gray-80 placeholder:text-gray-30 focus:border-blue-30 focus:outline-none"
            />
          </div>

          {/* 계정 목록 */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-body-small text-gray-40">
                검색 결과가 없습니다.
              </p>
            ) : (
              filtered.map((account, idx) => (
                <button
                  key={account.id}
                  type="button"
                  onClick={() => handleSelect(account.id)}
                  className={cn(
                    'flex w-full items-center gap-3 px-3 py-2 hover:bg-neutral-1 cursor-pointer',
                    idx < filtered.length - 1 && 'border-b border-neutral-2',
                  )}
                >
                  {account.picture ? (
                    <img
                      src={account.picture}
                      alt=""
                      className="size-10 shrink-0 rounded-full border border-neutral-1"
                    />
                  ) : (
                    <DefaultProfile className="size-10 shrink-0 rounded-full border border-neutral-1 text-gray-30" />
                  )}
                  <div className="flex min-w-0 flex-col items-start">
                    <div className="flex items-center gap-2.5">
                      <span className="max-w-[175px] truncate text-heading-small tracking-tight text-gray-80">
                        {account.name}
                      </span>
                      <span className="rounded-md2 bg-neutral-2 px-1.5 py-0.5 text-body-xsmall text-gray-50">
                        {account.tag}
                      </span>
                    </div>
                    <span className="truncate text-label-xsmall tracking-tight text-gray-50">
                      {account.email}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
