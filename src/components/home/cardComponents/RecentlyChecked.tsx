import Storage from '/public/icons/icon/storage.svg';
import ArrowRight from '/public/icons/icon/arrow_right2.svg';
import Folder from '/public/icons/icon/home_card_folder.svg';
import Depart from '/public/icons/icon/business_center_filled.svg';
import Manager from '/public/icons/icon/person_filled.svg';
import LoadingProfile from '/public/icons/icon/loading_profile.svg';
import Source from '/public/icons/icon/assignment_filled.svg';

const cardData = [
  {
    title: '일본 시장 진출 리서치 인수인계 text text text text',
    depart: '사업개발',
    manager: '이진수',
    source: 'Wiki',
    sourceTitle: '한도 계산 API 리팩토링 현황 공유 및 배포 일정 text text',
    sourceDescription:
      '현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 일정 운영 반영 시 유의사항을 함께 공유',
  },
  {
    title: '일본 시장 진출 리서치 인수인계 text text text text',
    depart: '사업개발',
    manager: '이진수',
    source: 'Wiki',
    sourceTitle: '한도 계산 API 리팩토링 현황 공유 및 배포 일정 text text',
    sourceDescription:
      '현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 일정 운영 반영 시 유의사항을 함께 공유',
  },
  {
    title: '일본 시장 진출 리서치 인수인계 text text text text',
    depart: '사업개발',
    manager: '이진수',
    source: 'Wiki',
    sourceTitle: '한도 계산 API 리팩토링 현황 공유 및 배포 일정 text text',
    sourceDescription:
      '현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 일정 운영 반영 시 유의사항을 함께 공유',
  },
];

const RecentlyChecked = () => {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex items-center">
        <div className="border-neutral-3 bg-blue-1 mr-2.5 rounded-lg border-[0.5px] p-1.5">
          <Storage className="h-5.5 w-5.5 text-blue-50" />
        </div>
        <h2 className="text-heading-large text-gray-80">최근 확인한 업무</h2>
        <ArrowRight className="relative left-1 h-6 w-6 cursor-pointer p-0.5 text-gray-50" />
      </header>

      <ul className="flex gap-4">
        {cardData.map((card, idx) => {
          return (
            <li
              key={idx}
              className="border-neutral-3 flex w-89.75 flex-col gap-3 rounded-2xl border bg-white px-5 py-4"
            >
              <Folder className="relative right-1 h-10.5 w-15.5" />

              <h3 className="text-heading-medium text-gray-80 truncate">{card.title}</h3>

              <div className="flex flex-col">
                <div className="flex flex-col gap-1.25">
                  <div className="flex gap-4">
                    <div className="flex items-center gap-1.5">
                      <Depart className="text-gray-20 h-4 w-4" />
                      <span className="text-body-small text-gray-50">담당 부서</span>
                    </div>
                    <span className="text-body-small text-gray-70">{card.depart} 팀</span>
                  </div>

                  <div className="flex gap-7">
                    <div className="flex items-center gap-1.5">
                      <Manager className="text-gray-20 h-4 w-4" />
                      <span className="text-body-small text-gray-50">담당자</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <LoadingProfile className="h-6.25 w-6.25" />
                      <span className="text-body-small text-gray-70">{card.manager}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-neutral-2 w-79.25 border"></div>

              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <Source className="text-gray-20 h-4 w-4" />
                  <span className="text-body-small text-gray-50">{card.source}</span>
                </div>
                <p className="text-body-small text-gray-80 line-clamp-1">{card.sourceTitle}</p>
                <p className="text-body-xsmall line-clamp-2 text-gray-50">{card.sourceDescription}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
};

export default RecentlyChecked;
