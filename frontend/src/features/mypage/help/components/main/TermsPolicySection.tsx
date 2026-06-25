import Link from 'next/link';

import { POLICY_ITEMS } from '@/features/mypage/help/constants/helpSections';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';

export default function TermsPolicySection() {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-text-normal-normal">약관 및 정책</h2>
        <p className="text-body-small text-text-normal-alternative">서비스 이용에 필요한 약관과 정책을 확인하세요.</p>
      </div>

      <div className="flex gap-5">
        {POLICY_ITEMS.map((item) => (
          <Link
            key={item.label}
            href="#"
            className="border-line-normal-neutral hover:bg-fill-normal-strong flex max-w-205 flex-1 items-center justify-between rounded-xl border px-5 py-3 transition-colors"
          >
            <span className="text-body-small text-text-normal-normal">{item.label}</span>
            <ArrowRight className="text-text-normal-alternative h-6 w-6" />
          </Link>
        ))}
      </div>
    </section>
  );
}
