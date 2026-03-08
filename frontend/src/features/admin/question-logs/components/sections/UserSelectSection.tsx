'use client';

import { useMemo, useState } from 'react';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconSearch from '@/public/icons/icon/search.svg';
import UnfoldMoreIcon from '@/public/icons/icon/unfold_more.svg';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

export interface UserOption {
  id: string;
  name: string;
  department: string;
  rank: string;
  picture: string | null;
}

interface UserSelectSectionProps {
  users: UserOption[];
  selectedUserId: string;
  onUserChange: (userId: string) => void;
}

/** 이용자 질문 기록 — 이용자 선택 섹션 */
const UserSelectSection = ({ users, selectedUserId, onUserChange }: UserSelectSectionProps) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const selectedUser = users.find((u) => u.id === selectedUserId);

  const filtered = useMemo(() => {
    const keyword = search.trim();
    if (!keyword) return users;
    return users.filter((u) => u.name.includes(keyword) || u.department.includes(keyword));
  }, [users, search]);

  const handleSelect = (userId: string) => {
    onUserChange(userId);
    setOpen(false);
    setSearch('');
  };

  return (
    <div className="flex w-[500px] flex-col gap-1.5">
      <h2 className="text-heading-small text-content-neutral">이용자 선택</h2>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              'border-edge-neutral text-body-small flex h-9 w-full cursor-pointer items-center justify-between rounded-lg border bg-fill-normal px-2.5 py-1.5 tracking-tight transition-colors',
              'hover:bg-fill-interaction-hover data-[state=open]:bg-fill-interaction-pressed data-[state=open]:border-edge-normal',
              selectedUser ? 'text-content-normal' : 'text-content-assistive',
            )}
          >
            <span className="truncate">
              {selectedUser ? `${selectedUser.name} (${selectedUser.department})` : '기록을 확인할 이용자를 선택하세요'}
            </span>
            <UnfoldMoreIcon className="size-6 shrink-0 text-content-alternative" />
          </button>
        </PopoverTrigger>

        <PopoverContent
          align="start"
          sideOffset={2}
          className="border-edge-strong flex h-[380px] w-[var(--radix-popover-trigger-width)] flex-col gap-3 rounded-xl p-2.5"
        >
          {/* 검색 */}
          <label className="bg-fill-interaction-hover border-edge-primary flex h-10 items-center gap-1.5 rounded-lg border px-3">
            <IconSearch className="text-content-assistive size-5 shrink-0" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="담당자 검색"
              className="text-body-small text-content-normal placeholder:text-content-assistive w-full bg-transparent outline-none"
            />
          </label>

          {/* 유저 리스트 */}
          <div className="flex flex-1 flex-col gap-1 overflow-y-auto px-0.5">
            {filtered.map((user) => (
              <button
                key={user.id}
                type="button"
                onClick={() => handleSelect(user.id)}
                className={cn(
                  'flex h-10 shrink-0 cursor-pointer items-center gap-2 rounded-xl px-2 py-1',
                  user.id === selectedUserId ? 'bg-fill-interaction-hover' : 'hover:bg-fill-strong',
                )}
              >
                <DefaultProfile className="text-content-assistive size-7 shrink-0 rounded-full" />
                <span className="text-body-small text-content-neutral min-w-0 flex-1 truncate text-left tracking-tight">
                  {user.name}
                </span>
                <span className="text-body-xsmall text-content-assistive max-w-[72px] shrink-0 truncate tracking-tight">
                  {user.department}
                </span>
              </button>
            ))}

            {filtered.length === 0 && (
              <div className="text-body-xsmall text-content-assistive flex flex-1 items-center justify-center">
                검색 결과가 없습니다.
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>

      <p className="text-label-xsmall text-content-alternative">선택한 이용자의 활동 내역이 표시됩니다.</p>
    </div>
  );
};

export default UserSelectSection;
