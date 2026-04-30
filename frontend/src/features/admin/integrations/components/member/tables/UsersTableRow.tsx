'use client';

import { cn } from '@/shared/utils/cn';

import { getServicesGroupClass, TABLE_BODY_ROW_CLASS } from '../../../constants/memberUiConfig';
import type { IntegrationService } from '../../../types/integrationModel';
import type { MemberDisplayRow } from '../../../types/memberDisplayModel';
import { isRowFullyLinked, selectCellMode } from '../../../utils/usersTableHelpers';
import type { AccountOption } from './AccountSelectDropdown';
import AccountEditCell from './cells/AccountEditCell';
import KeycloakUserCell from './cells/KeycloakUserCell';
import LinkedAccountCell from './cells/LinkedAccountCell';
import UnusedTagCell from './cells/UnusedTagCell';

interface UsersTableRowProps {
  row: MemberDisplayRow;
  services: IntegrationService[];
  isEditMode: boolean;
  accountOptionsByService: Partial<Record<IntegrationService, AccountOption[]>>;
  selectedAccounts?: Record<string, Partial<Record<IntegrationService, AccountOption>>>;
  onAccountSelect?: (userKey: string, service: IntegrationService, account: AccountOption) => void;
  onToggleUnused?: (userKey: string, service: IntegrationService, unused: boolean) => void;
}

export default function UsersTableRow({
  row: { renderKey, row, displayStatusByService },
  services,
  isEditMode,
  accountOptionsByService,
  selectedAccounts,
  onAccountSelect,
  onToggleUnused,
}: UsersTableRowProps) {
  const isAllLinked = isRowFullyLinked(displayStatusByService, services);
  const isSingleService = services.length === 1;

  return (
    <div className={TABLE_BODY_ROW_CLASS}>
      <div className={cn('size-2 shrink-0 rounded-full', isAllLinked ? 'bg-status-positive' : 'bg-accent-red')} />
      <KeycloakUserCell userName={row.userName} isSingleService={isSingleService} />
      <div className={getServicesGroupClass(isSingleService)}>
        {services.map((service) => {
          const status = displayStatusByService[service];
          const info = row.serviceInfoByService[service];
          const result = selectCellMode({ service, status, isEditMode });
          const key = `${renderKey}-${service}`;

          switch (result.mode) {
            case 'linked':
              return <LinkedAccountCell key={key} info={info} />;
            case 'unused-tag':
              // result.status는 '미사용' | '미등록'으로 narrow됨 — cast 불필요
              return <UnusedTagCell key={key} status={result.status} />;
            case 'account-edit':
              return (
                <AccountEditCell
                  key={key}
                  status={result.status}
                  options={accountOptionsByService[service] ?? []}
                  selectedAccount={selectedAccounts?.[row.userKey]?.[service]}
                  onSelect={(account) => onAccountSelect?.(row.userKey, service, account)}
                  onToggleUnused={(unused) => onToggleUnused?.(row.userKey, service, unused)}
                />
              );
            default: {
              // exhaustive — CellModeResult.mode에 새 모드 추가 시 컴파일 에러로 알림
              const _exhaustive: never = result;
              return null;
            }
          }
        })}
      </div>
    </div>
  );
}
