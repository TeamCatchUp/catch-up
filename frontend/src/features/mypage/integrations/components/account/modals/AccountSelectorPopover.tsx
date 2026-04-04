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
export default function AccountSelectorPopover({
  open,
  onOpenChange,
  options,
  selectedAccount,
  placeholder,
  searchValue,
  onSearchValueChange,
  onSelect,
}: AccountSelectorPopoverProps) {
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={`border-edge-neutral bg-fill-normal flex w-full cursor-pointer items-center rounded-[10px] border text-left ${
            selectedAccount ? 'gap-4 px-3 py-2.5' : 'h-11.5 justify-between px-2.5 py-1.5'
          }`}
        >
          {selectedAccount ? (
            <>
              <DefaultProfile className="text-content-assistive size-10 shrink-0 rounded-full" />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-center gap-2.5">
                  <span className="text-heading-small text-content-normal max-w-33.25 truncate">
                    {selectedAccount.userName}
                  </span>
                  <span className="rounded-md2 bg-fill-interaction-hover text-body-xsmall text-content-alternative shrink-0 px-1.5 py-0.5">
                    {selectedAccount.accountId}
                  </span>
                </div>
                <span className="text-body-xsmall text-content-alternative truncate">{selectedAccount.userEmail}</span>
              </div>
              <UnfoldMore className="text-content-assistive size-6 shrink-0" />
            </>
          ) : (
            <>
              <span className="text-body-small text-content-assistive truncate">{placeholder}</span>
              <UnfoldMore className="text-content-assistive size-5.5 shrink-0" />
            </>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={6}
        avoidCollisions={false}
        className="border-edge-normal shadow-dropdown-menu w-84 rounded-xl p-0"
      >
        <Command className="gap-2.5 rounded-xl py-2.5">
          <div className="px-2.5">
            <CommandInput
              value={searchValue}
              onValueChange={onSearchValueChange}
              placeholder="이름, 이메일, 아이디를 검색하세요."
            />
          </div>
          <CommandList className="max-h-77.5 px-0 py-0">
            <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
            {options.map((option) => (
              <CommandItem
                key={option.key}
                value={`${option.userName} ${option.userEmail} ${option.accountId}`}
                onSelect={() => onSelect(option.key)}
                className="border-edge-assistive data-[selected=true]:bg-fill-strong gap-3 rounded-none border-b px-3 py-2"
              >
                <DefaultProfile className="text-content-assistive size-10 shrink-0 rounded-full" />
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <div className="flex items-center gap-2.5">
                    <span className="text-heading-small text-content-normal max-w-40 truncate">{option.userName}</span>
                    <span className="rounded-md2 bg-fill-interaction-hover text-body-xsmall text-content-alternative shrink-0 px-1.5 py-0.5">
                      {option.accountId}
                    </span>
                  </div>
                  <span className="text-label-xsmall text-content-alternative truncate">{option.userEmail}</span>
                </div>
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
