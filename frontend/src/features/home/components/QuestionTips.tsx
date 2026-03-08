import Image from 'next/image';

import Book from '@/public/icons/icon/book.svg';

interface QuestionTipsProps {
  onTipClick: (query: string) => void;
}

const tipData = [
  {
    title: '과거 문의 대응 사례 찾기',
    description: '비슷한 문의를 찾아\n원인부터 결론까지 바로 가져와요.',
    image: '/image/home/light/past-inquiry.png',
    query:
      '슬랙에서 [문의 내용/에러로그]와 관련된 "예전에 해결된 사례"를 찾아, 바로 답하세요. 답변에는 원인, 해결 방법, 최종 결론(어떻게 해결됐는지), 담당자(누가 처리했는지), 확인할 곳(슬랙 원문 링크/관련 지라 티켓/관련 PR)을 반드시 포함하세요. 관련 사례를 못 찾으면, 이 문제를 가장 잘 아는 담당자 1~3명을 추천하세요.',
  },
  {
    title: '업무 진행 상황 확인',
    description: '지라, PR, 커밋, 슬랙 등을 묶어\n실제 진행상황을 한 번에 파악해요.',
    image: '/image/home/light/work-progress.jpg',
    query:
      '[기능명/티켓번호]의 진행 상황을 확인해 지금 상태를 답하세요. 지라 상태만 보여주지 말고, 깃허브(PR/커밋)와 슬랙 논의까지 함께 확인해 "실제로 어디까지 됐는지" 정리하세요. 답변에는 현재 상태, 담당자, 마지막 작업 시각, 지금 남은 일, 확인할 곳(지라/PR/슬랙 링크)을 반드시 포함하세요. 관련 정보를 못 찾으면 어떤 정보가 부족한지 한 줄로 말하고, 다음에 뭘 입력하면 되는지 안내하세요.',
  },
  {
    title: '중복 논의 여부 확인',
    description: '이전에 결정한 내용이 있는지,\n그때 기준과 이유를 바로 보여줘요.',
    image: '/image/home/light/duplicate-discussion.jpg',
    query:
      '[논의/요구사항]이 예전에 이미 논의됐고 결론이 난 적이 있는지 확인해 답하세요. 유사한 과거 안건이 있으면 그때의 결론(진행/보류/반려)과 이유(왜 그렇게 결정했는지), 누가 결정에 참여했는지, 지금 다시 추진하려면 어떤 조건이 달라져야 하는지를 정리하세요. 답변에는 결론, 근거 요약, 담당자/참여자, 확인할 곳(지라 티켓/슬랙 스레드/관련 PR 링크)을 반드시 포함하세요. 관련 기록을 못 찾으면 "신규 안건"으로 표시하고, 바로 다음에 해야 할 최소 확인 2가지를 제안하세요.',
  },
  {
    title: '장애 원인 추적',
    description: '최근 변경을 시간순으로 훑어\n가장 의심되는 원인부터 좁혀가요.',
    image: '/image/home/light/incident-tracking.jpg',
    query:
      '배포 직후 발생한 [에러/증상]의 원인을 찾기 위해, 최근 [기간] 동안의 변경 사항을 전부 훑어 "원인 후보"를 우선순위로 정리하세요. 코드 변경(PR/커밋)뿐 아니라 지라 이슈 변경과 슬랙에서 논의된 배포/장애/설정 변경까지 함께 확인해, 무엇이 가장 의심스러운지와 왜 그런지 설명하세요. 답변에는 원인 후보 Top 3, 각 후보의 근거(무슨 변경이 있었는지), 관련 담당자, 그리고 확인할 곳(지라/PR·커밋/슬랙 링크)을 반드시 포함하세요. 관련 변경을 못 찾으면 범위를 줄이기 위해 내가 추가로 줘야 할 정보 1가지만 요청하세요.',
  },
  {
    title: '히스토리 따라잡기',
    description: '주요 변경과 논의를 묶어\n참고해야 할 자료를 한 번에 정리해요.',
    image: '/image/home/light/history-catchup.jpg',
    query:
      '신규 입사자가 [프로젝트/모듈/기능명]의 히스토리를 혼자 파악할 수 있게 정리하세요. 왜 만들어졌는지(배경), 중요한 변경/결정이 있었던 순간들, 관련된 사람(주요 작업자/논의자), 지금 참고해야 할 자료를 한 번에 보여주세요. 답변에는 핵심 타임라인, 담당자, 그리고 확인할 곳(지라 티켓/PR·커밋/슬랙 스레드 링크)을 반드시 포함하세요. 관련 기록을 못 찾으면 어떤 단서가 부족한지 한 줄로 말하고, 다음에 뭘 입력하면 되는지 안내하세요.',
  },
  {
    title: '담당자&대리인 찾기',
    description: '가장 가까이 작업한 사람을 찾아\n지금 연결해야 할 담당자를 추천해요.',
    image: '/image/home/light/find-assignee.png',
    query:
      '[기능/모듈/에러]를 지금 가장 빨리 해결할 수 있는 사람을 추천하세요. 먼저 "원 담당자(주요 작업자)"를 찾고, 현재 응답이 어려운 상태(부재/휴가/연락 불가)라면 "대리인"을 1~3명 추천하세요. 추천에는 왜 이 사람인지(최근 작업/리뷰/관련 PR·커밋 근거), 지금 연락 가능한지(슬랙 상태가 보이면 포함), 그리고 바로 확인할 곳(관련 PR·커밋/지라 티켓/슬랙 스레드 링크)을 반드시 포함하세요. 관련 기록이 부족하면 내가 추가로 줄 정보 1가지만 요청하세요.',
  },
];

// 2개씩 묶어서 행 생성
const rows = [tipData.slice(0, 2), tipData.slice(2, 4), tipData.slice(4, 6)];

const QuestionTips = ({ onTipClick }: QuestionTipsProps) => {
  return (
    <section className="flex w-268 flex-col gap-4">
      <header className="flex items-center gap-3">
        <div className="border-edge-neutral bg-fill-primary-assistive flex h-8 w-8 items-center justify-center rounded-lg border-[0.5px]">
          <Book className="h-6 w-6 text-icon-primary" />
        </div>
        <h2 className="text-heading-large text-content-normal">질문 작성을 도와드릴게요!</h2>
      </header>

      <div className="flex flex-col gap-3">
        {rows.map((row, rowIdx) => (
          <div key={rowIdx} className="flex gap-6">
            {row.map((tip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onTipClick(tip.query)}
                className="border-edge-neutral flex flex-1 cursor-pointer items-center overflow-hidden rounded-xl border bg-fill-normal text-left"
              >
                <div className="flex flex-[1_0_0] flex-col gap-1.5 p-5">
                  <h3 className="text-heading-medium text-content-neutral">{tip.title}</h3>
                  <p className="text-body-small whitespace-pre-line text-content-alternative">{tip.description}</p>
                </div>
                <div className="relative aspect-260/118 flex-[1_0_0] overflow-hidden">
                  <Image src={tip.image} alt={tip.title} fill className="object-cover dark:hidden" />
                  <Image
                    src={tip.image.replace('/light/', '/dark/')}
                    alt={tip.title}
                    fill
                    className="hidden object-cover dark:block"
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
