import Image from 'next/image';
import Link from 'next/link';

import { GUIDE_CARDS } from '@/features/mypage/help/constants/helpSections';

export default function GuideTutorialSection() {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-text-normal-normal">가이드 · 튜토리얼 보기</h2>
        <p className="text-body-small text-text-normal-alternative">주요 기능부터 활용 팁까지 단계별로 안내합니다.</p>
      </div>

      <ul className="flex flex-wrap gap-6">
        {GUIDE_CARDS.map((card) => (
          <li
            key={card.id}
            className="border-line-normal-neutral bg-fill-normal-normal hover:bg-fill-normal-strong flex max-w-134.25 min-w-61.75 flex-1 flex-col overflow-hidden rounded-xl border transition-colors"
          >
            <Link href={`/mypage/help/tutorial/${card.id}`}>
              <div className="border-line-normal-neutral relative aspect-59/25 w-full border-b">
                <Image src={card.image} alt={card.title} fill className="object-cover" />
              </div>
              <div className="flex flex-col gap-2 p-5">
                <h3 className="text-heading-small text-text-normal-normal">{card.title}</h3>
                <p className="text-body-small text-text-normal-alternative whitespace-pre-line">{card.description}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
