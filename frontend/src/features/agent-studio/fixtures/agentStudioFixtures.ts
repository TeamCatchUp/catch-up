import type {
  AgentStudioCardModel,
  AgentStudioFilter,
  AgentStudioFilterItem,
  AgentStudioSettingsFixture,
} from '../types/agentStudioModel';

export const AGENT_STUDIO_FILTERS: readonly AgentStudioFilterItem[] = [
  { value: 'all', label: '전체' },
  { value: 'active', label: '운영중' },
  { value: 'draft', label: '제작중' },
  { value: 'inactive', label: '사용 안함' },
];

export const AGENT_STUDIO_LIST_FIXTURE: readonly AgentStudioCardModel[] = [
  {
    id: 'inquiry-report-agent',
    status: 'active',
    title: '문의 대응 리포트 만들기',
    description:
      '현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 운영 반영 시 유의사항을 함께 공유합니다.',
    authorName: '이진수',
    updatedAtLabel: '2020.00.00(월)',
  },
];

export const AGENT_STUDIO_SETTINGS_FIXTURE: AgentStudioSettingsFixture = {
  title: '문의 대응 리포트 만들기',
  descriptionLines: [
    '채널톡에 고객 문의가 들어오면, 사내 지식 정보를 활용해 문의 대응 리포트를 자동으로 생성합니다.',
    '생성된 리포트는 Slack으로 자동으로 발송됩니다.',
  ],
  channelTalkChannelLabel: '채널톡 내 채널을 선택해주세요',
  quietPeriodLabel: '1분',
  slackWorkspaceName: 'Catch Up',
  slackChannelLabel: 'Slack 내 채널을 선택해주세요',
  instructionHintText: '프로젝트 맥락과 업무 스타일을 반영할 수 있어요.',
  instructionMaxLength: 500,
};

export function getAgentCardsByStatus(filter: AgentStudioFilter): readonly AgentStudioCardModel[] {
  if (filter === 'all') return AGENT_STUDIO_LIST_FIXTURE;

  return AGENT_STUDIO_LIST_FIXTURE.filter((item) => item.status === filter);
}
