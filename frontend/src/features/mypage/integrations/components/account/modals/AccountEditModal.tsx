import { useMemo, useState } from 'react';

import ArrowDown from '@/public/icons/icon/arrow_down-2.svg';
import Cancel from '@/public/icons/icon/cancel.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error-1.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';

import type { MemberIntegrationRow } from '../../../types/integrations';
import AccountSelectorPopover, { type AccountOption } from './AccountSelectorPopover';
import ReasonRadioGroup, { type ReasonOption } from './ReasonRadioGroup';

const EDIT_REASON_OPTIONS: ReasonOption[] = [
  { key: 'not-my-account', label: '내가 사용하는 계정이 아니에요.' },
  { key: 'changed-account', label: '사용하는 계정을 바꾸었어요.' },
  { key: 'custom', label: '직접 입력' },
];

interface AccountEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedRow: MemberIntegrationRow;
  allRows: MemberIntegrationRow[];
  serviceName: string;
}

/** 계정 정보 수정 모달 */
const AccountEditModal = ({ open, onOpenChange, selectedRow, allRows, serviceName }: AccountEditModalProps) => {
  const [selectedReason, setSelectedReason] = useState('not-my-account');
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
      deduped.set(key, { key, userName: row.userName, userEmail: row.email, accountId: jiraAccountId });
    });
    return Array.from(deduped.values());
  }, [allRows]);

  const selectedAccount = useMemo(
    () => accountOptions.find((o) => o.key === selectedAccountKey) ?? null,
    [accountOptions, selectedAccountKey],
  );

  const currentJiraAccountId = selectedRow.accountIdByService.jira ?? '-';
  const isSubmitDisabled = !selectedAccount || (selectedReason === 'custom' && customReason.trim().length === 0);

  const resetFormState = () => {
    setSelectedReason('not-my-account');
    setCustomReason('');
    setSelectedAccountKey('');
    setSearchValue('');
    setAccountPopoverOpen(false);
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) resetFormState();
    onOpenChange(nextOpen);
  };

  const handleClose = () => handleDialogOpenChange(false);

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent hideClose className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4">
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-gray-80">계정 정보 수정하기</DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-gray-50" />
          </button>
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

              <AccountSelectorPopover
                open={accountPopoverOpen}
                onOpenChange={setAccountPopoverOpen}
                options={accountOptions}
                selectedAccount={selectedAccount}
                placeholder={`변경할 ${serviceName} 계정을 선택해주세요.`}
                searchValue={searchValue}
                onSearchValueChange={setSearchValue}
                onSelect={(key) => {
                  setSelectedAccountKey(key);
                  setAccountPopoverOpen(false);
                }}
              />

              <p className="text-label-xsmall text-red-50 flex items-center gap-0.5">
                <IconError className="size-4" />
                반드시 본인의 계정을 연동해주세요.
              </p>
            </div>

            <div className="border-neutral-1 absolute top-[101px] left-1/2 -translate-x-1/2 rounded-full border bg-gray-80 p-1">
              <ArrowDown className="size-[18px] text-white" />
            </div>
          </div>

          <ReasonRadioGroup
            title="수정 사유를 선택해주세요."
            options={EDIT_REASON_OPTIONS}
            selectedKey={selectedReason}
            onSelect={setSelectedReason}
            customValue={customReason}
            onCustomValueChange={setCustomReason}
          />

          <p className="text-label-xsmall mt-4 text-gray-50">
            자신의 계정이 아닌 타인의 계정을 연동하면 Catch Up이 드리는 답변의 내용이 부정확해지거나 관련 내용이 누락될 수 있어요.
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
