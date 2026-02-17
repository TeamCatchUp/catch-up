import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import UnfoldMore from '@/public/icons/icon/unfold_more.svg';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/shared/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';

export interface AccountOption {
  key: string;
  userName: string;
  userEmail: string;
  accountId: string;
}

interface AccountSelectorPopoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  options: AccountOption[];
  selectedAccount: AccountOption | null;
  placeholder: string;
  searchValue: string;
  onSearchValueChange: (value: string) => void;
  onSelect: (key: string) => void;
}

/** 계정 선택 드롭다운 (Popover + Command) */
const AccountSelectorPopover = ({
  open,
  onOpenChange,
  options,
  selectedAccount,
  placeholder,
  searchValue,
  onSearchValueChange,
  onSelect,
}: AccountSelectorPopoverProps) => (
  <Popover open={open} onOpenChange={onOpenChange}>
    <PopoverTrigger asChild>
      <button
        type="button"
        className="border-neutral-3 text-body-small text-gray-30 flex h-[46px] w-full cursor-pointer items-center justify-between rounded-lg border bg-white px-2.5 py-1.5 text-left"
      >
        <span className="truncate">
          {selectedAccount ? `${selectedAccount.userName} (${selectedAccount.accountId})` : placeholder}
        </span>
        <UnfoldMore className="text-gray-40 size-5.5 shrink-0" />
      </button>
    </PopoverTrigger>
    <PopoverContent
      side="bottom"
      align="start"
      sideOffset={6}
      avoidCollisions={false}
      className="border-neutral-4 shadow-dropdown-menu w-[336px] rounded-xl p-0"
    >
      <Command className="gap-2.5 rounded-xl py-2.5">
        <div className="px-2.5">
          <CommandInput
            value={searchValue}
            onValueChange={onSearchValueChange}
            placeholder="이름, 이메일, 아이디를 검색하세요."
          />
        </div>
        <CommandList className="max-h-[310px] px-0 py-0">
          <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
          {options.map((option) => (
            <CommandItem
              key={option.key}
              value={`${option.userName} ${option.userEmail} ${option.accountId}`}
              onSelect={() => onSelect(option.key)}
              className="border-neutral-2 data-[selected=true]:bg-neutral-1 gap-3 rounded-none border-b px-3 py-2"
            >
              <DefaultProfile className="border-neutral-1 text-gray-30 size-10 shrink-0 rounded-full border" />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-center gap-2.5">
                  <span className="text-heading-small text-gray-80 max-w-[160px] truncate">{option.userName}</span>
                  <span className="rounded-md2 bg-neutral-2 text-body-xsmall shrink-0 px-1.5 py-0.5 text-gray-50">
                    {option.accountId}
                  </span>
                </div>
                <span className="text-label-xsmall truncate text-gray-50">{option.userEmail}</span>
              </div>
            </CommandItem>
          ))}
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
);

export default AccountSelectorPopover;
