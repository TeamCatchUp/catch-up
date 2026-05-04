'use client';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import {
  FLEX_COLUMN_CELL_CLASS,
  getKeycloakColumnClass,
  KEYCLOAK_USER_CELL_CLASS,
} from '../../../../constants/memberUiConfig';

interface KeycloakUserCellProps {
  userName: string;
  isSingleService: boolean;
}

/** Keycloak 사용자 셀 — 프로필 + 이름 (모든 mode 공통) */
export default function KeycloakUserCell({ userName, isSingleService }: KeycloakUserCellProps) {
  return (
    <div className={cn(getKeycloakColumnClass(isSingleService), KEYCLOAK_USER_CELL_CLASS)}>
      <DefaultProfile className="border-fill-strong text-content-assistive size-5 shrink-0 rounded-full border" />
      <div className={FLEX_COLUMN_CELL_CLASS}>
        <span className="text-body-small text-content-normal truncate">{userName}</span>
      </div>
    </div>
  );
}
