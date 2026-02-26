import Image from 'next/image';

import { SUPPORT_CARDS } from '@/features/mypage/help/constants/helpSections';
import { Badge } from '@/shared/components/ui/badge';

const AccountSupportSection = () => {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-gray-80">계정 및 지원 안내</h2>
        <p className="text-body-small text-gray-50">계정 설정과 지원 정보를 확인하세요.</p>
      </div>

      <ul className="flex gap-5">
        {SUPPORT_CARDS.map((card) => (
          <li
            key={card.title}
            className="border-neutral-3 flex w-58.75 shrink-0 flex-col overflow-hidden rounded-xl border bg-white"
          >
            <div className="border-neutral-3 relative aspect-292/128 w-full border-b opacity-80">
              <Image src={card.image} alt={card.title} fill className="object-cover" />
            </div>
            <div className="flex flex-col gap-2 px-5 py-4">
              <div className="flex items-center gap-2">
                <h3 className="text-heading-small text-gray-80">{card.title}</h3>
                <Badge className="rounded-md2 px-1.5 py-0.5">{card.tag}</Badge>
              </div>
              <p className="text-body-xsmall whitespace-pre-line text-gray-50">{card.description}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default AccountSupportSection;
