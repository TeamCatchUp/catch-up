'use client';

// 고객정보 섹션 — 접기/펴기. open 상태를 자체 소유하고 본문은 Collapsible로 렌더.
// 이름/이메일/전화번호/유선번호 를 OriginalCustomer 에서 렌더. 좌측 라벨 컬럼 138px 고정.

import { useState } from 'react';

import Collapsible from '@/features/hybrid-search/components/original/Collapsible';
import type { OriginalCustomer } from '@/features/hybrid-search/types/originalApi';
import CallIcon from '@/public/icons/icon/call.svg';
import CardClientIcon from '@/public/icons/icon/card_client.svg';
import ChevronIcon from '@/public/icons/icon/dropdown_down.svg';
import MailIcon from '@/public/icons/icon/mail.svg';
import PersonIcon from '@/public/icons/icon/person.svg';
import PhoneIcon from '@/public/icons/icon/phone.svg';

import InfoFieldLabel from './InfoFieldLabel';

interface CustomerInfoProps {
  customer: OriginalCustomer | undefined;
}

interface CustomerRowProps {
  icon: typeof PersonIcon;
  label: string;
  value: string | undefined;
}

function CustomerRow({ icon: Icon, label, value }: CustomerRowProps) {
  const display = value?.trim();
  return (
    <div className="flex items-center gap-10">
      <InfoFieldLabel icon={Icon} text={label} />
      <span className="text-body-small text-content-neutral min-w-0 flex-1 truncate">
        {display ?? <span className="text-content-assistive">없음</span>}
      </span>
    </div>
  );
}

export default function CustomerInfo({ customer }: CustomerInfoProps) {
  const [open, setOpen] = useState(true);

  const header = (
    <div className="flex w-full items-center gap-4 py-4">
      <CardClientIcon className="text-icon-neutral h-5.5 w-5.5 shrink-0" />
      <span className="text-body-small text-content-alternative flex-1 text-left">고객정보</span>
      <ChevronIcon
        aria-hidden
        className={`text-icon-neutral h-4.5 w-4.5 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
      />
    </div>
  );

  return (
    <section className="bg-fill-strong border-edge-neutral w-full rounded-xl border px-5">
      <Collapsible open={open} onOpenChange={setOpen} header={header}>
        <div className="flex flex-col gap-3 pb-4">
          <CustomerRow icon={PersonIcon} label="이름" value={customer?.name} />
          <CustomerRow icon={MailIcon} label="이메일" value={customer?.email} />
          <CustomerRow icon={PhoneIcon} label="전화번호" value={customer?.mobile_number} />
          <CustomerRow icon={CallIcon} label="유선번호" value={customer?.landline_number} />
        </div>
      </Collapsible>
    </section>
  );
}
