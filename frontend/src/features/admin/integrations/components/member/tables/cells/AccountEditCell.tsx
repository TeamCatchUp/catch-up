'use client';

import { BODY_SERVICE_COLUMN_CLASS } from '../../../../constants/memberUiConfig';
import type { UnlinkedStatus } from '../../../../utils/usersTableHelpers';
import AccountSelectDropdown, { type AccountOption } from '../AccountSelectDropdown';

interface AccountEditCellProps {
  status: UnlinkedStatus;
  options: AccountOption[];
  selectedAccount: AccountOption | undefined;
  onSelect: (account: AccountOption) => void;
  onToggleUnused: (unused: boolean) => void;
}

/** mode='account-edit' 셀 — 수정 모드 계정 선택 dropdown wrapper */
export default function AccountEditCell({
  status,
  options,
  selectedAccount,
  onSelect,
  onToggleUnused,
}: AccountEditCellProps) {
  return (
    <div className={BODY_SERVICE_COLUMN_CLASS}>
      <AccountSelectDropdown
        status={status}
        options={options}
        selectedAccount={selectedAccount}
        onSelect={onSelect}
        onToggleUnused={onToggleUnused}
      />
    </div>
  );
}
