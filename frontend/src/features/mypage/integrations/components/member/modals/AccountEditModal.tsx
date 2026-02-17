import { useMemo, useState } from 'react';

import ArrowDown from '@/public/icons/icon/arrow_down.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error.svg'
import UnfoldMore from '@/public/icons/icon/unfold_more.svg';
import { Button } from '@/shared/components/ui/button';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/shared/components/ui/command';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { cn } from '@/shared/utils/cn';

import type { MemberIntegrationRow } from '../../../types/integrations';

type EditReason = 'not-my-account' | 'changed-account' | 'custom';

const EDIT_REASON_OPTIONS: { key: EditReason; label: string }[] = [
  { key: 'not-my-account', label: '내가 사용하는 계정이 아니에요.' },
  { key: 'changed-account', label: '사용하는 계정을 바꾸었어요.' },
  { key: 'custom', label: '직접 입력' },
];

interface AccountOption {
  key: string;
  userName: string;
  userEmail: string;
  accountId: string;
}

interface AccountEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedRow: MemberIntegrationRow;
  allRows: MemberIntegrationRow[];
}

interface ReasonRadioProps {
  selected: boolean;
  onClick: () => void;
  ariaLabel: string;
}

const ReasonRadio = ({ selected, onClick, ariaLabel }: ReasonRadioProps) => {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className="relative mt-px size-6 shrink-0 cursor-pointer"
    >
      <span
        className={cn(
          'absolute inset-[3px] rounded-full border',
          selected ? 'border-blue-50' : 'border-neutral-4 bg-white',
        )}
      />
      {selected && <span className="bg-blue-50 absolute inset-[7px] rounded-full" />}
    </button>
  );
};

const AccountEditModal = ({ open, onOpenChange, selectedRow, allRows }: AccountEditModalProps) => {
  const [selectedReason, setSelectedReason] = useState<EditReason>('not-my-account');
  const [customReason, setCustomReason] = useState('');
  const [selectedAccountKey, setSelectedAccountKey] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [accountPopoverOpen, setAccountPopoverOpen] = useState(false);

  const accountOptions = useMemo<AccountOption[]>(() => {
    const deduped = new Map<string, AccountOption>();

    allRows.forEach((row) => {
      const jiraAccountId = row.accountIdByService.jira;
      if (!jiraAccountId) return;

      const key = `${jiraAccountId}:${row.email}`;
      if (deduped.has(key)) return;

      deduped.set(key, {
        key,
        userName: row.userName,
        userEmail: row.email,
        accountId: jiraAccountId,
      });
    });

    return Array.from(deduped.values());
  }, [allRows]);

  const selectedAccount = useMemo(
    () => accountOptions.find((option) => option.key === selectedAccountKey) ?? null,
    [accountOptions, selectedAccountKey],
  );

  const currentJiraAccountId = selectedRow.accountIdByService.jira ?? '-';
  const showAccountError = !selectedAccount;
  const requiresCustomReason = selectedReason === 'custom';
  const isSubmitDisabled = showAccountError || (requiresCustomReason && customReason.trim().length === 0);

  const resetFormState = () => {
    setSelectedReason('not-my-account');
    setCustomReason('');
    setSelectedAccountKey('');
    setSearchValue('');
    setAccountPopoverOpen(false);
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      resetFormState();
    }
    onOpenChange(nextOpen);
  };

  const handleClose = () => {
    handleDialogOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4">
        <div className="flex h-9 items-center">
          <DialogTitle className="text-heading-medium text-gray-80">계정 정보 수정하기</DialogTitle>
        </div>

        <div className="border-neutral-3 max-h-[378px] w-full overflow-y-auto border-t pt-4">
          <div className="relative w-full overflow-clip rounded-xl border border-neutral-3">
            <div className="bg-neutral-1 border-neutral-3 flex flex-col gap-2 border-b p-4">
              <span className="text-body-small text-gray-80">현재 연결된 계정</span>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <DefaultProfile className="border-neutral-1 text-gray-30 size-6.25 shrink-0 rounded-full border" />
                  <span className="text-body-small text-gray-80 truncate">{selectedRow.userName}</span>
                  <span className="rounded-md2 bg-neutral-2 text-body-xsmall shrink-0 px-1.5 py-0.5 text-gray-50">
                    {currentJiraAccountId}
                  </span>
                </div>
                <span className="text-body-xsmall truncate text-gray-50">{selectedRow.email}</span>
              </div>
            </div>

            <div className="flex flex-col gap-1.5 bg-white p-4">
              <div className="text-body-small text-gray-80 flex items-center gap-1">
                새 계정 선택
                <span className="bg-red-50 block size-[5px] shrink-0 rounded-full" />
              </div>

              <Popover open={accountPopoverOpen} onOpenChange={setAccountPopoverOpen}>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="border-neutral-3 text-body-small text-gray-30 flex h-9 w-full items-center justify-between rounded-lg border bg-white px-2.5 py-1.5 text-left"
                  >
                    <span className="truncate">
                      {selectedAccount ? `${selectedAccount.userName} (${selectedAccount.accountId})` : '변경할 Jira 계정을 선택해주세요.'}
                    </span>
                    <UnfoldMore className="size-6 shrink-0 text-gray-40" />
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  align="start"
                  sideOffset={6}
                  className="border-neutral-4 shadow-dropdown-menu w-[336px] rounded-xl p-0"
                >
                  <Command className="gap-2.5 rounded-xl py-2.5">
                    <div className="px-2.5">
                      <CommandInput
                        value={searchValue}
                        onValueChange={setSearchValue}
                        placeholder="이름, 이메일, 아이디를 검색하세요."
                      />
                    </div>
                    <CommandList className="max-h-[310px] px-0 py-0">
                      <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
                      {accountOptions.map((option) => (
                        <CommandItem
                          key={option.key}
                          value={`${option.userName} ${option.userEmail} ${option.accountId}`}
                          onSelect={() => {
                            setSelectedAccountKey(option.key);
                            setAccountPopoverOpen(false);
                          }}
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

              {showAccountError && (
                <p className="text-label-xsmall text-red-50 flex items-center gap-0.5">
                  <IconError className="size-4"/>
                  반드시 본인의 계정을 연동해주세요.
                </p>
              )}
            </div>

            <div className="border-neutral-1 absolute top-[101px] left-1/2 -translate-x-1/2 rounded-full border bg-gray-80 p-1">
              <ArrowDown className="size-[18px] text-white" />
            </div>
          </div>

          <div className="mt-4 flex w-full flex-col gap-2">
            <div className="text-body-small text-gray-80 flex items-center gap-1">
              수정 사유를 선택해주세요.
              <span className="bg-red-50 block size-[5px] shrink-0 rounded-full" />
            </div>

            <div className="border-neutral-1 flex flex-col gap-4 rounded-xl border px-4 py-4">
              {EDIT_REASON_OPTIONS.map((option) => {
                if (option.key !== 'custom') {
                  return (
                    <div key={option.key} className="flex w-full items-center gap-3">
                      <ReasonRadio
                        selected={selectedReason === option.key}
                        onClick={() => setSelectedReason(option.key)}
                        ariaLabel={option.label}
                      />
                      <span className="text-body-small text-gray-70">{option.label}</span>
                    </div>
                  );
                }

                return (
                  <div key={option.key} className="flex w-full items-start gap-3">
                    <ReasonRadio
                      selected={selectedReason === option.key}
                      onClick={() => setSelectedReason(option.key)}
                      ariaLabel={option.label}
                    />
                    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                      <span className="text-body-small text-gray-70">{option.label}</span>
                      <Input
                        inputSize="lg"
                        value={customReason}
                        onChange={(event) => setCustomReason(event.target.value)}
                        placeholder="반려 사유를 입력해주세요."
                        className="h-[46px]"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <p className="text-label-xsmall mt-4 text-gray-50">
            자신의 계정이 아닌 타인의 계정을 연동하면 Catch Up이 드리는 답변의 내용이 부정확해지거나 관련 내용이
            누락될 수 있어요.
          </p>
        </div>

        <div className="mt-1 flex h-9 w-full items-start justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button variant="capsule-solid-primary" size="md" disabled={isSubmitDisabled} onClick={handleClose}>
            수정하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AccountEditModal;
