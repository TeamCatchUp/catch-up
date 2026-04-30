'use client';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import {
  KEYCLOAK_COLUMN_CLASS,
  KEYCLOAK_USER_CELL_CLASS,
  KEYCLOAK_USER_NAME_CLASS,
} from '../../../../constants/memberUiConfig';

interface KeycloakUserCellProps {
  userName: string;
  isSingleService: boolean;
}

/** Keycloak 사용자 셀 — 프로필 + 이름 (모든 mode 공통) */
export default function KeycloakUserCell({ userName, isSingleService }: KeycloakUserCellProps) {
  return (
    <div className={cn(KEYCLOAK_COLUMN_CLASS, !isSingleService && 'max-w-35', KEYCLOAK_USER_CELL_CLASS)}>
      <DefaultProfile className="border-fill-strong text-content-assistive size-5 shrink-0 rounded-full border" />
      <div className={KEYCLOAK_USER_NAME_CLASS}>
        <span className="text-body-small text-content-normal truncate">{userName}</span>
      </div>
    </div>
  );
}
