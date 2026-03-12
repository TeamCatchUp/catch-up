import type { TipData } from '@/shared/types/template';

export type { TemplateField, TemplateSegment, TipData } from '@/shared/types/template';
export { buildQueryFromTemplate } from '@/shared/types/template';

export const tipData: TipData[] = [
  {
    title: '반복 문의 대응',
    description: '비슷한 문의를 찾아\n원인부터 결론까지 바로 가져와요.',
    image: '/image/home/light/past-inquiry.png',
    template: [
      { field: 'channel' },
      '에서 ',
      { field: 'content' },
      ' 관련 해결 사례를 찾아 원인, 해결 방법, 담당자, 출처 링크를 답하세요. 사례가 없으면 관련 담당자 1~3명을 추천하세요.',
    ],
    fields: [
      { key: 'channel', placeholder: '채널' },
      { key: 'content', placeholder: '문의 내용/에러로그' },
    ],
  },
  {
    title: '이슈 현황 파악',
    description: '지라, PR, 커밋, 슬랙 등을 묶어\n실제 진행상황을 한 번에 파악해요.',
    image: '/image/home/light/work-progress.jpg',
    template: [
      { field: 'ticket' },
      '의 현재 상태를 Jira, GitHub, Slack을 교차 확인해 실제 진행 상황, 담당자, 마지막 작업 시각, 잔여 작업, 출처 링크를 답하세요.',
    ],
    fields: [{ key: 'ticket', placeholder: '기능명/티켓번호' }],
  },
  {
    title: '신규 입사자 온보딩',
    description: '주요 변경과 논의를 묶어\n참고해야 할 자료를 한 번에 정리해요.',
    image: '/image/home/light/history-catchup.jpg',
    template: [
      { field: 'project' },
      '의 히스토리를 핵심 타임라인, 주요 결정 배경, 관련 담당자, 참고 자료 링크로 정리하세요. ',
      { field: 'role' },
      ' 신규 입사자 기준으로 설명하세요.',
    ],
    fields: [
      { key: 'project', placeholder: '프로젝트/모듈' },
      { key: 'role', placeholder: '직군' },
    ],
  },
  {
    title: '장애 원인 추적',
    description: '최근 변경을 시간순으로 훑어\n가장 의심되는 원인부터 좁혀가요.',
    image: '/image/home/light/incident-tracking.jpg',
    template: [
      { field: 'period' },
      ' 내 ',
      { field: 'service' },
      '에서 발생한 ',
      { field: 'error' },
      '의 원인을 PR, Jira, Slack 변경 이력 기반으로 Top 3 후보와 근거, 담당자, 출처 링크로 답하세요.',
    ],
    fields: [
      { key: 'error', placeholder: '에러/증상' },
      { key: 'period', placeholder: '기간' },
      { key: 'service', placeholder: '서비스/모듈' },
    ],
  },
  {
    title: '중복 논의 방어',
    description: '이전에 결정한 내용이 있는지,\n그때 기준과 이유를 바로 보여줘요.',
    image: '/image/home/light/duplicate-discussion.jpg',
    template: [
      { field: 'team' },
      ' 관련, ',
      { field: 'topic' },
      '의 과거 논의 여부를 확인해 결론, 결정 근거, 참여자, 출처 링크를 답하세요. 기록이 없으면 신규 안건으로 표시하고 다음 확인 사항 2가지를 제안하세요.',
    ],
    fields: [
      { key: 'topic', placeholder: '논의/요구사항' },
      { key: 'team', placeholder: '관련 팀' },
    ],
  },
  {
    title: '담당자 추천',
    description: '가장 가까이 작업한 사람을 찾아\n지금 연결해야 할 담당자를 추천해요.',
    image: '/image/home/light/find-assignee.png',
    template: [
      { field: 'teamRole' },
      ' 내 ',
      { field: 'target' },
      '의 원 담당자를 찾고, 부재 시 대리인 1~3명을 작업 근거, 연락 가능 여부, 출처 링크와 함께 추천하세요.',
    ],
    fields: [
      { key: 'target', placeholder: '기능/모듈/에러' },
      { key: 'teamRole', placeholder: '팀/직군' },
    ],
  },
];
