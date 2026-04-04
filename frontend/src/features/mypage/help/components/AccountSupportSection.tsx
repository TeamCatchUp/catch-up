import Image from 'next/image';
import Link from 'next/link';

import { SUPPORT_CARDS } from '@/features/mypage/help/constants/helpSections';
import { Badge } from '@/shared/components/ui/badge';

export default function AccountSupportSection() {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-content-normal">계정 및 지원 안내</h2>
        <p className="text-body-small text-content-alternative">계정 설정과 지원 정보를 확인하세요.</p>
      </div>

      <ul className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-5">
        {SUPPORT_CARDS.map((card) => (
          <li
            key={card.title}
            className="border-edge-neutral bg-fill-normal flex max-w-100 flex-col overflow-hidden rounded-xl border transition-colors hover:bg-fill-strong"
          >
            <Link href={`/mypage/help/support/${card.id}`}>
              <div className="border-edge-neutral relative aspect-292/128 w-full border-b">
                <Image src={card.image} alt={card.title} fill className="object-cover dark:hidden" />
                <Image
                  src={card.image.replace('/light/', '/dark/')}
                  alt={card.title}
                  fill
                  className="hidden object-cover dark:block"
                />
              </div>
              <div className="flex flex-col gap-2 px-5 py-4">
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <h3 className="text-heading-small text-content-normal">{card.title}</h3>
                  <Badge className="shrink-0 rounded-md2 px-1.5 py-0.5">{card.tag}</Badge>
                </div>
                <p className="text-body-xsmall text-content-alternative whitespace-pre-line">{card.description}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
