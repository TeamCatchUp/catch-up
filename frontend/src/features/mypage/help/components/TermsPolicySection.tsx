import Link from 'next/link';

import { POLICY_ITEMS } from '@/features/mypage/help/constants/helpSections';
import ArrowRight from '@/public/icons/icon/arrow_right.svg';

const TermsPolicySection = () => {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-gray-80">약관 및 정책</h2>
        <p className="text-body-small text-gray-50">
          서비스 이용을 위한 약관과 정책을 확인하세요.
        </p>
      </div>

      <div className="flex gap-5">
        {POLICY_ITEMS.map((item) => (
          <Link
            key={item.label}
            href="#"
            className="border-neutral-3 flex w-122.5 shrink-0 items-center justify-between rounded-xl border px-5 py-3 transition-colors hover:bg-neutral-1"
          >
            <span className="text-body-small text-gray-80">{item.label}</span>
            <ArrowRight className="h-6 w-6 text-gray-50" />
          </Link>
        ))}
      </div>
    </section>
  );
};

export default TermsPolicySection;
