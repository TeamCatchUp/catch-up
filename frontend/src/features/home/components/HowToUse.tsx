import Image from 'next/image';
import Link from 'next/link';

import ArrowRight from '@/public/icons/icon/arrow_right.svg';
import Explore from '@/public/icons/icon/explore.svg';

const cardData = [
  {
    tutorialId: 1,
    title: '검색 한 번으로 찾는 업무 정보',
    description: '정보를 찾는 시간,\n이제 일하는 시간으로 사용하세요.',
    image: '/image/home/light/search-work-info.jpg',
  },
  {
    tutorialId: 2,
    title: '원하는 답을 한 번에 얻는 비결',
    description: '질문이 구체적일수록 AI가 더 정확하게 대답해요.\n어떻게 질문을 작성하면 좋은지 알려드려요.',
    image: '/image/home/light/accurate-answers.jpg',
  },
  {
    tutorialId: 3,
    title: '정확도를 올리는 출처 확인 방법',
    description: '답변 뒤에 붙은 작은 번호를 누르면,\nAI가 참고한 자료의 출처로 바로 이동해요.',
    image: '/image/home/light/verify-sources.jpg',
  },
];

const HowToUse = () => {
  return (
    <section className="flex w-268 flex-col gap-4">
      <header className="flex items-center gap-3">
        <div className="border-edge-neutral bg-fill-primary-assistive flex h-8 w-8 items-center justify-center rounded-lg border-[0.5px]">
          <Explore className="text-icon-primary h-6 w-6" />
        </div>
        <h2 className="text-heading-large text-content-normal">Catch Up을 활용하는 방법</h2>
      </header>

      <ul className="flex gap-6">
        {cardData.map((card, idx) => (
          <li
            key={idx}
            className="border-edge-neutral bg-fill-normal flex flex-1 flex-col overflow-hidden rounded-2xl border"
          >
            <div className="border-edge-neutral relative h-36 w-full border-b">
              <Image src={card.image} alt={card.title} fill className="object-cover dark:hidden" />
              <Image
                src={card.image.replace('/light/', '/dark/')}
                alt={card.title}
                fill
                className="hidden object-cover dark:block"
              />
            </div>

            <div className="flex flex-col gap-3 p-4">
              <div className="flex flex-col gap-1">
                <h3 className="text-heading-medium text-content-normal">{card.title}</h3>
                <p className="text-body-small text-content-alternative whitespace-pre-line">{card.description}</p>
              </div>

              <Link
                href={`/mypage/help/tutorial/${card.tutorialId}`}
                className="border-edge-neutral active:border-edge-strong active:bg-fill-interaction-pressed hover:border-edge-normal hover:bg-fill-interaction-hover bg-fill-normal ml-auto flex h-7.5 cursor-pointer items-center gap-1 rounded-lg border px-2 py-1"
              >
                <span className="text-body-xsmall text-content-normal whitespace-nowrap">더 알아보기</span>
                <ArrowRight className="text-icon-normal h-6 w-6" />
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};

export default HowToUse;
