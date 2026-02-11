import Book from '/public/icons/icon/book.svg';

interface QuestionTipsProps {
  onTipClick: (query: string) => void;
}

const tipData = [
  {
    title: '과거 문의 대응 사례 찾기',
    description: '비슷한 문의를 찾아\n원인부터 결론까지 바로 가져와요.',
    image: '/image/과거문의.png',
    query: '과거에 비슷한 문의가 있었는지 찾아줘',
  },
  {
    title: '업무 진행 상황 확인',
    description: '지라, PR, 커밋, 슬랙 등을 묶어\n실제 진행상황을 한 번에 파악해요.',
    image: '/image/업무진행상황확인.jpg',
    query: '현재 업무 진행 상황을 확인해줘',
  },
  {
    title: '중복 논의 여부 확인',
    description: '이전에 결정한 내용이 있는지,\n그때 기준과 이유를 바로 보여줘요.',
    image: '/image/중복논의.jpg',
    query: '이전에 논의된 내용이 있는지 확인해줘',
  },
  {
    title: '장애 원인 추적',
    description: '최근 변경을 시간순으로 훑어\n가장 의심되는 원인부터 좁혀가요.',
    image: '/image/장애원인추적.jpg',
    query: '최근 장애의 원인을 추적해줘',
  },
  {
    title: '히스토리 따라잡기',
    description: '주요 변경과 논의를 묶어\n참고해야 할 자료를 한 번에 정리해요.',
    image: '/image/히스토리.jpg',
    query: '최근 주요 변경 히스토리를 정리해줘',
  },
  {
    title: '담당자&대리인 찾기',
    description: '가장 가까이 작업한 사람을 찾아\n지금 연결해야 할 담당자를 추천해요.',
    image: '/image/담당자대리인찾기.png',
    query: '이 업무의 담당자를 찾아줘',
  },
];

// 2개씩 묶어서 행 생성
const rows = [tipData.slice(0, 2), tipData.slice(2, 4), tipData.slice(4, 6)];

const QuestionTips = ({ onTipClick }: QuestionTipsProps) => {
  return (
    <section className="flex w-full max-w-[1072px] flex-col gap-4">
      <header className="flex items-center gap-3">
        <div className="border-neutral-3 bg-blue-1 flex h-8 w-8 items-center justify-center rounded-lg border-[0.5px]">
          <Book className="h-6 w-6 text-blue-50" />
        </div>
        <h2 className="text-heading-large text-gray-80">질문 작성을 도와드릴게요!</h2>
      </header>

      <div className="flex flex-col gap-3">
        {rows.map((row, rowIdx) => (
          <div key={rowIdx} className="flex gap-6">
            {row.map((tip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onTipClick(tip.query)}
                className="border-neutral-3 flex flex-1 cursor-pointer items-center overflow-hidden rounded-xl border bg-white text-left"
              >
                <div className="flex flex-1 flex-col gap-1.5 p-5">
                  <h3 className="text-heading-medium text-gray-70">{tip.title}</h3>
                  <p className="text-body-small whitespace-pre-line text-gray-50">{tip.description}</p>
                </div>
                <div className="relative flex-1 self-stretch">
                  <img
                    src={tip.image}
                    alt={tip.title}
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                </div>
              </button>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
};

export default QuestionTips;
