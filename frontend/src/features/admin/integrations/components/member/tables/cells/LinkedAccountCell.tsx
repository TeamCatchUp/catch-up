'use client';

import Image from 'next/image';

import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import { cn } from '@/shared/utils/cn';

import {
  BODY_SERVICE_COLUMN_CLASS,
  FLEX_COLUMN_CELL_CLASS,
  SERVICE_ACCOUNT_IDENTIFIER_CLASS,
} from '../../../../constants/memberUiConfig';
import type { PreMappingInfo } from '../../../../types/integrationApi';

interface LinkedAccountCellProps {
  info: PreMappingInfo | undefined;
}

/** mode='linked' 셀 — 매핑된 계정의 프로필 + 이름 + 이메일 표시 */
export default function LinkedAccountCell({ info }: LinkedAccountCellProps) {
  return (
    <div className={cn(BODY_SERVICE_COLUMN_CLASS, 'relative flex-col items-start gap-0.5 overflow-hidden rounded-xl')}>
      <div className="flex w-full shrink-0 items-center gap-2">
        {info?.picture ? (
          <Image
            src={info.picture}
            alt=""
            width={20}
            height={20}
            className="border-fill-strong size-5 shrink-0 rounded-full border"
          />
        ) : (
          <DefaultProfile className="border-fill-strong text-content-assistive size-5 shrink-0 rounded-full border" />
        )}
        <div className={FLEX_COLUMN_CELL_CLASS}>
          <span className="text-body-xsmall text-content-normal truncate">{info?.name ?? '-'}</span>
        </div>
      </div>
      <div className={SERVICE_ACCOUNT_IDENTIFIER_CLASS}>
        <span className="text-body-xsmall text-content-alternative truncate">{info?.identifier ?? '-'}</span>
      </div>
    </div>
  );
}
