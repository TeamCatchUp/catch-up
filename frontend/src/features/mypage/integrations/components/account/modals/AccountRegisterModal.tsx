import { useMemo, useState } from 'react';

import Cancel from '@/public/icons/icon/cancel.svg';
import IconError from '@/public/icons/icon/error-1.svg';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/shared/components/ui/dialog';
import type { IntegrationService } from '@/shared/types/integrationService';

import type { MemberIntegrationRow } from '../../../types/integrations';
import AccountSelectorPopover, { type AccountOption } from './AccountSelectorPopover';
import ReasonRadioGroup, { type ReasonOption } from './ReasonRadioGroup';

const REGISTER_REASON_OPTIONS: ReasonOption[] = [
  { key: 'new-tool', label: '새롭게 이 협업 툴을 사용하게 되었어요.' },
  { key: 'new-integration', label: 'Catch Up에 신규 협업 툴이 연동되었어요.' },
  { key: 'custom', label: '직접 입력' },
];

interface AccountRegisterModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  allRows: MemberIntegrationRow[];
  service: IntegrationService;
  serviceName: string;
}

/** 계정 등록 모달 */
const AccountRegisterModal = ({ open, onOpenChange, allRows, service, serviceName }: AccountRegisterModalProps) => {
  const [selectedReason, setSelectedReason] = useState('new-tool');
  const [customReason, setCustomReason] = useState('');
  const [selectedAccountKey, setSelectedAccountKey] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [accountPopoverOpen, setAccountPopoverOpen] = useState(false);

  const accountOptions = useMemo<AccountOption[]>(() => {
    const deduped = new Map<string, AccountOption>();
    allRows.forEach((row) => {
      const accountId = row.accountIdByService[service];
      if (!accountId) return;
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

  const isSubmitDisabled = !selectedAccount || (selectedReason === 'custom' && customReason.trim().length === 0);

  const resetFormState = () => {
    setSelectedReason('new-tool');
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
        className="border-neutral-3 shadow-modal max-w-[400px] gap-2 rounded-2xl border bg-white px-5 pt-3 pb-4"
      >
        <div className="flex h-9 items-center justify-between">
          <DialogTitle className="text-heading-medium text-gray-80">계정 등록하기</DialogTitle>
          <button type="button" onClick={handleClose} className="cursor-pointer" aria-label="닫기">
            <Cancel className="size-5 text-gray-50" />
          </button>
        </div>

        <div className="border-neutral-3 max-h-[378px] w-full overflow-y-auto border-t pt-4">
          <div className="flex flex-col gap-1.5">
            <AccountSelectorPopover
              open={accountPopoverOpen}
              onOpenChange={setAccountPopoverOpen}
              options={accountOptions}
              selectedAccount={selectedAccount}
              placeholder={`사용중인 ${serviceName} 계정을 선택하세요.`}
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

          <ReasonRadioGroup
            title="등록 사유를 선택해주세요."
            options={REGISTER_REASON_OPTIONS}
            selectedKey={selectedReason}
            onSelect={setSelectedReason}
            customValue={customReason}
            onCustomValueChange={setCustomReason}
            customPlaceholder="등록 사유를 입력해주세요."
          />

          <p className="text-label-xsmall mt-4 text-gray-50">
            자신의 계정이 아닌 타인의 계정을 연동하면 Catch Up이 드리는 답변의 내용이 부정확해지거나 관련 내용이 누락될
            수 있어요.
          </p>
        </div>

        <div className="mt-1 flex h-9 w-full items-start justify-end gap-2.5">
          <Button variant="capsule-outline-mono" size="md" onClick={handleClose}>
            취소
          </Button>
          <Button variant="capsule-solid-primary" size="md" disabled={isSubmitDisabled} onClick={handleClose}>
            계정 등록하기
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AccountRegisterModal;
