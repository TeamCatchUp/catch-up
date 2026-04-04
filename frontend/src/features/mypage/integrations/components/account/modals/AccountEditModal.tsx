import { useMemo, useState } from 'react';

import ArrowDown from '@/public/icons/icon/arrow_down-2.svg';
import Cancel from '@/public/icons/icon/cancel.svg';
import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import IconError from '@/public/icons/icon/error-1.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { IntegrationService } from '@/shared/types/integrationService';

import type { MemberIntegrationRow } from '../../../types/integrationModel';
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
  service: IntegrationService;
  serviceName: string;
}

/** 계정 정보 수정 모달 */
export default function AccountEditModal({
  open,
  onOpenChange,
  selectedRow,
  allRows,
  service,
  serviceName,
}: AccountEditModalProps) {
  const [selectedReason, setSelectedReason] = useState('not-my-account');
  const [customReason, setCustomReason] = useState('');
  const [selectedAccountKey, setSelectedAccountKey] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [accountPopoverOpen, setAccountPopoverOpen] = useState(false);

  const accountOptions = useMemo<AccountOption[]>(() => {
    const deduped = new Map<string, AccountOption>();
    allRows.forEach((row) => {
      const info = row.serviceInfoByService[service];
      if (!info?.identifier) return;
      const accountId = info.identifier;
      const key = `${accountId}:${row.email}`;
      if (deduped.has(key)) return;
      deduped.set(key, { key, userName: row.userName, userEmail: row.email, accountId });
    });
    return Array.from(deduped.values());
  }, [allRows, service]);

  const selectedAccount = useMemo(
    () => accountOptions.find((o) => o.key === selectedAccountKey) ?? null,
    [accountOptions, selectedAccountKey],
  );

  const currentAccountId = selectedRow.serviceInfoByService[service]?.identifier ?? '-';
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
      <DialogContent
        hideClose
        className="border-edge-neutral shadow-modal bg-fill-normal max-w-100 gap-2 rounded-2xl border px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-content-normal">계정 정보 수정하기</DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer" aria-label="닫기">
            <Cancel className="text-content-alternative size-5" />
          </button>
        </div>

        <div className="border-edge-neutral max-h-94.5 w-full overflow-y-auto border-t pt-4">
          <div className="border-edge-neutral relative w-full overflow-clip rounded-xl border">
            <div className="bg-fill-strong border-edge-neutral flex flex-col gap-2 border-b p-4">
              <span className="text-body-small text-content-normal">현재 연결된 계정</span>
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-2">
                  <DefaultProfile className="text-content-assistive size-6.25 shrink-0 rounded-full" />
                  <span className="text-body-small text-content-normal truncate">{selectedRow.userName}</span>
                  <span className="rounded-md2 bg-fill-interaction-hover text-body-xsmall text-content-alternative shrink-0 px-1.5 py-0.5">
                    {currentAccountId}
                  </span>
                </div>
                <span className="text-body-xsmall text-content-alternative truncate">{selectedRow.email}</span>
              </div>
            </div>

            <div className="bg-fill-normal flex flex-col gap-1.5 p-4">
              <div className="text-body-small text-content-normal flex items-center gap-1">
                새 계정 선택
                <span className="block size-1.25 shrink-0 rounded-full bg-red-50" />
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

              <p className="text-label-xsmall flex items-center gap-0.5 text-red-50">
                <IconError className="size-4" />
                반드시 본인의 계정을 연동해주세요.
              </p>
            </div>

            <div className="border-edge-assistive bg-gray-80 absolute top-25.25 left-1/2 -translate-x-1/2 rounded-full border p-1">
              <ArrowDown className="size-4.5 text-white" />
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

          <p className="text-label-xsmall text-content-alternative mt-4">
            자신의 계정이 아닌 타인의 계정을 연동하면 Catch Up이 드리는 답변의 내용이 부정확해지거나 관련 내용이 누락될
            수 있어요.
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
}
