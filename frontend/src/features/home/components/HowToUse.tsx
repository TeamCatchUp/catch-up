import ArrowRight from '/public/icons/icon/arrow_right.svg';
import Explore from '/public/icons/icon/explore.svg';
import HowToUse1 from '/public/icons/icon/how_to_use_1.svg';
import HowToUse2 from '/public/icons/icon/how_to_use_2.svg';
import HowToUse3 from '/public/icons/icon/how_to_use_3.svg';
import WebTraffic from '/public/icons/icon/web_traffic.svg';

const cardData = [
  {
    image: HowToUse1,
    label: '탐색 시간 3배 이상 단축',
    title: '검색 한 번으로 찾는 업무 정보',
    description: '정보를 찾는 시간,\n이제 일하는 시간으로 사용하세요.',
  },
  {
    image: HowToUse2,
    label: '핵심 정보 누락률 최대 70% 감소',
    title: '시작부터 끝까지 관리하는 업무 이력',
    description: '업무 정리부터 매뉴얼 작성, 미팅 기록까지,\n모든 과정이 지식으로 남습니다.',
  },
  {
    image: HowToUse3,
    label: '자료 정리 시간 최대 90% 감소',
    title: '툴마다 흩어진 업무, 한 번에 통합',
    description: '여러 틀에 흩어진 정보들을\n자동으로 수집하고, 한 곳에 보관합니다.',
  },
];

const HowToUse = () => {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-center gap-3">
        <div className="border-neutral-3 bg-blue-1 rounded-lg border-[0.5px] p-1.5">
          <Explore className="h-5 w-5 text-blue-50" />
        </div>
        <h2 className="text-heading-large text-gray-80">Catch Up을 활용하는 방법</h2>
      </header>

      <ul className="flex gap-5">
        {cardData.map((card, idx) => {
          const CardImg = card.image;
          return (
            <li key={idx} className="border-neutral-3 w-89.75 rounded-2xl border">
              <CardImg className="h-[151.5px] w-89.5 rounded-t-2xl" />

              <div className="flex h-48 w-88.5 flex-col gap-3 rounded-b-2xl bg-white p-4 text-gray-50">
                <div className="rounded-md2 bg-neutral-2 flex w-max items-center gap-1 px-1.5 py-0.5">
                  <WebTraffic className="h-4 w-4 text-gray-50" />
                  <span className="text-body-xsmall relative top-[0.5px]">{card.label}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="text-heading-medium text-gray-80">{card.title}</h3>
                  <p className="text-body-small whitespace-pre-line text-gray-50">{card.description}</p>
                </div>

                <button
                  type="button"
                  className="border-neutral-3 active:border-neutral-5 active:bg-neutral-3 hover:border-neutral-4 hover:bg-neutral-2 mt-1 mr-px ml-auto flex h-9 w-25.25 cursor-pointer items-center gap-1 rounded-lg border bg-white px-2 py-1.5"
                >
                  <span className="text-body-xsmall text-gray-80 relative top-[0.5px] left-px whitespace-nowrap">
                    더 알아보기
                  </span>
                  <ArrowRight className="text-gray-70 relative left-1 flex h-5 w-5" />
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default HowToUse;
