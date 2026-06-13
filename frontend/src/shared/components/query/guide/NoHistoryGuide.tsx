'use client';

import IconArrowForward from '@/public/icons/icon/arrow_forward.svg';
import IconLightbulb from '@/public/icons/icon/lightbulb.svg';

interface NoHistoryStep {
  title: string;
  highlight: string;
  suffix: string;
  body: string;
  prefix?: string;
}

const NO_HISTORY_STEPS: NoHistoryStep[] = [
  {
    title: 'Step 1',
    highlight: '어떤 업무에 대한 질문',
    suffix: '인지 적어주세요.',
    body: 'Jira 티켓 번호, 기능 이름, PR 제목처럼 업무를 떠올릴 수 있는 단어면 충분해요.',
  },
  {
    title: 'Step 2',
    prefix: '그 업무에서 ',
    highlight: '무엇이 궁금',
    suffix: '한지를 함께 적어주세요.',
    body: '왜 이렇게 결정됐는지, 중간에 변경된 내용이 있는지, 업무에 관하여 궁금한 지점을 자연스럽게 써주세요.',
  },
  {
    title: 'Step 3',
    prefix: '필요하다면, ',
    highlight: '어디에서 확인',
    suffix: '하고 싶은지 덧붙여 주세요.',
    body: 'Jira 티켓이나 PR, 커밋, Confluence 문서 등 특정 툴을 함께 적으면 더 정확한 결과를 찾을 수 있어요.',
  },
] as const;

const NO_HISTORY_EXAMPLES = [
  'PAY-214 결제 수단 추가 왜 이렇게 구현됐어?',
  '로그인 리팩토링 관련해서 Slack에서 논의된 내용 뭐야?',
  '#482 PR이랑 연결된 Jira 티켓 뭐였지?',
  '정산 배치 작업 배포 전에 주의사항 정리된 거 있어?',
] as const;

interface NoHistoryGuideProps {
  onExampleClick?: (query: string) => void;
}

export const NoHistoryGuide = ({ onExampleClick }: NoHistoryGuideProps) => {
  return (
    <div className="no-scrollbar flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      <div className="flex items-center gap-5">
        <div className="bg-fill-primary-normal-assistive flex size-11.25 shrink-0 items-center justify-center rounded-xl p-1">
          <IconLightbulb className="text-accent-red-orange-default size-6" />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-heading-small text-text-normal-normal">이렇게 질문해보세요!</p>
          <p className="text-body-xsmall text-text-normal-alternative">
            업무를 기준으로 질문하면 관련된 모든 정보를 한 번에 찾을 수 있어요.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {NO_HISTORY_STEPS.map((step) => (
          <div key={step.title} className="bg-fill-primary-normal-assistive flex flex-col gap-2 rounded-xl p-2.5">
            <span className="text-body-xsmall bg-accent-information-lighten text-text-normal-alternative w-fit rounded-full px-1.5 py-0.5">
              {step.title}
            </span>
            <p className="text-body-xsmall text-text-normal-strong leading-5">
              {step.prefix ?? ''}
              <span className="text-red-orange-50">{step.highlight}</span>
              {step.suffix}
            </p>
            <p className="text-body-xsmall text-text-normal-alternative leading-5">{step.body}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2.5">
        <span className="text-body-xsmall text-text-normal-alternative px-1">질문 예시</span>
        <div className="flex flex-col gap-1">
          {NO_HISTORY_EXAMPLES.slice(0, 3).map((example) => (
            <button
              key={example}
              onClick={() => onExampleClick?.(example)}
              className="group hover:bg-fill-normal-interaction-hover text-body-small text-text-normal-normal flex h-10 cursor-pointer items-center rounded-xl px-2 text-left transition-colors"
            >
              <span className="flex-1">{example}</span>
              <IconArrowForward className="text-icon-normal-neutral ml-2 h-5 w-5 opacity-0 transition-opacity group-hover:opacity-100" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
