import Image from 'next/image';
import Link from 'next/link';

import { GUIDE_CARDS } from '@/features/mypage/help/constants/helpSections';

const GuideTutorialSection = () => {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-heading-large text-content-normal">가이드 · 튜토리얼 보기</h2>
        <p className="text-body-small text-content-alternative">주요 기능부터 활용 팁까지 단계별로 안내합니다.</p>
      </div>

      <ul className="flex gap-6">
        {GUIDE_CARDS.map((card) => (
          <li
            key={card.id}
            className="border-edge-neutral flex w-79.25 shrink-0 flex-col overflow-hidden rounded-xl border bg-fill-normal"
          >
            <Link href={`/mypage/help/tutorial/${card.id}`}>
              <div className="border-edge-neutral relative aspect-59/25 w-full border-b">
                <Image src={card.image} alt={card.title} fill className="object-cover" />
              </div>
              <div className="flex flex-col gap-2 p-5">
                <h3 className="text-heading-small text-content-normal">{card.title}</h3>
                <p className="text-body-xsmall whitespace-pre-line text-content-alternative">{card.description}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default GuideTutorialSection;
