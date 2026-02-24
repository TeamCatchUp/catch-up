import type {
  DailyTokenUsage,
  LimitReleaseRequest,
  OrgMember,
  TokenUsageRankingEntry,
  TokenUsageSummary,
  TotalQuestionCount,
  TotalTokenUsageTrend,
} from '../types/tokenUsage';

export const MOCK_SUMMARY: TokenUsageSummary = {
  total_cost: 34.09,
  status: 'normal',
};

export const MOCK_DAILY_USAGE: DailyTokenUsage[] = [
  { date: '2026-01-15', cost: 4.12, model_name: 'GPT-4o' },
  { date: '2026-01-16', cost: 1.87, model_name: 'GPT-4o' },
  { date: '2026-01-17', cost: 7.55, model_name: 'GPT-4o' },
  { date: '2026-01-18', cost: 1.24, model_name: 'GPT-4o' },
  { date: '2026-01-19', cost: 3.31, model_name: 'GPT-4o' },
  { date: '2026-01-20', cost: 2.43, model_name: 'GPT-4o' },
  { date: '2026-01-21', cost: 2.08, model_name: 'GPT-4o' },
  { date: '2026-01-22', cost: 2.03, model_name: 'GPT-4o' },
  { date: '2026-01-23', cost: 1.11, model_name: 'GPT-4o' },
  { date: '2026-01-24', cost: 0.69, model_name: 'GPT-4o' },
  { date: '2026-01-25', cost: 4.34, model_name: 'GPT-4o' },
];

export const MOCK_TOTAL_TREND: TotalTokenUsageTrend[] = [
  { date: '2026-01-15', cumulative_tokens: 4120 },
  { date: '2026-01-16', cumulative_tokens: 5990 },
  { date: '2026-01-17', cumulative_tokens: 13540 },
  { date: '2026-01-18', cumulative_tokens: 14780 },
  { date: '2026-01-19', cumulative_tokens: 18090 },
  { date: '2026-01-20', cumulative_tokens: 20520 },
  { date: '2026-01-21', cumulative_tokens: 22600 },
  { date: '2026-01-22', cumulative_tokens: 24630 },
  { date: '2026-01-23', cumulative_tokens: 25740 },
  { date: '2026-01-24', cumulative_tokens: 26430 },
  { date: '2026-01-25', cumulative_tokens: 30770 },
];

export const MOCK_QUESTION_COUNTS: TotalQuestionCount[] = [
  { date: '2026-01-15', count: 0 },
  { date: '2026-01-16', count: 0 },
  { date: '2026-01-17', count: 0 },
  { date: '2026-01-18', count: 0 },
  { date: '2026-01-19', count: 120 },
  { date: '2026-01-20', count: 130 },
  { date: '2026-01-21', count: 125 },
  { date: '2026-01-22', count: 140 },
  { date: '2026-01-23', count: 110 },
  { date: '2026-01-24', count: 135 },
  { date: '2026-01-25', count: 140 },
];

/* ─── 조직 토큰 사용량 ─── */

export const MOCK_ORG_MEMBERS: OrgMember[] = [
  { id: '1', name: '팀원G', team: '부서H', position: '경영진', role: '루트 어드민', tokenEnabled: true, cost: 34.1 },
  { id: '2', name: '직원20', team: '부서M', position: '팀원', role: '일반', tokenEnabled: false, cost: 12.5 },
  { id: '3', name: '직원04', team: '부서B', position: '팀장', role: '일반', tokenEnabled: true, cost: 28.3 },
  { id: '4', name: '직원10', team: '부서I', position: '팀원', role: '일반', tokenEnabled: true, cost: 9.7 },
  { id: '5', name: '직원25', team: '부서F', position: '팀원', role: '일반', tokenEnabled: true, cost: 22.0 },
  { id: '6', name: '직원28', team: '부서N', position: '팀원', role: '일반', tokenEnabled: false, cost: 5.2 },
  { id: '7', name: '직원29', team: '부서D', position: '팀장', role: '일반', tokenEnabled: true, cost: 18.6 },
  { id: '8', name: '직원21', team: '부서G', position: '팀원', role: '일반', tokenEnabled: true, cost: 7.4 },
  { id: '9', name: '직원18', team: '부서K', position: '팀원', role: '일반', tokenEnabled: true, cost: 15.1 },
  { id: '10', name: '직원22', team: '부서C', position: '팀원', role: '일반', tokenEnabled: true, cost: 3.8 },
  { id: '11', name: '직원02', team: '부서A', position: '팀장', role: '일반', tokenEnabled: true, cost: 11.9 },
];

export const MOCK_ORG_DAILY_USAGE: DailyTokenUsage[] = [
  { date: '2026-01-15', cost: 12.5, model_name: 'GPT-4o' },
  { date: '2026-01-16', cost: 8.3, model_name: 'GPT-4o' },
  { date: '2026-01-17', cost: 22.1, model_name: 'GPT-4o' },
  { date: '2026-01-18', cost: 5.8, model_name: 'GPT-4o' },
  { date: '2026-01-19', cost: 15.2, model_name: 'GPT-4o' },
  { date: '2026-01-20', cost: 10.4, model_name: 'GPT-4o' },
  { date: '2026-01-21', cost: 9.1, model_name: 'GPT-4o' },
  { date: '2026-01-22', cost: 8.7, model_name: 'GPT-4o' },
  { date: '2026-01-23', cost: 4.6, model_name: 'GPT-4o' },
  { date: '2026-01-24', cost: 3.0, model_name: 'GPT-4o' },
  { date: '2026-01-25', cost: 18.9, model_name: 'GPT-4o' },
];

export const MOCK_ORG_TOTAL_TREND: TotalTokenUsageTrend[] = [
  { date: '2026-01-15', cumulative_tokens: 12500 },
  { date: '2026-01-16', cumulative_tokens: 20800 },
  { date: '2026-01-17', cumulative_tokens: 42900 },
  { date: '2026-01-18', cumulative_tokens: 48700 },
  { date: '2026-01-19', cumulative_tokens: 63900 },
  { date: '2026-01-20', cumulative_tokens: 74300 },
  { date: '2026-01-21', cumulative_tokens: 83400 },
  { date: '2026-01-22', cumulative_tokens: 92100 },
  { date: '2026-01-23', cumulative_tokens: 96700 },
  { date: '2026-01-24', cumulative_tokens: 99700 },
  { date: '2026-01-25', cumulative_tokens: 118600 },
];

export const MOCK_ORG_QUESTION_COUNTS: TotalQuestionCount[] = [
  { date: '2026-01-15', count: 0 },
  { date: '2026-01-16', count: 0 },
  { date: '2026-01-17', count: 0 },
  { date: '2026-01-18', count: 85 },
  { date: '2026-01-19', count: 310 },
  { date: '2026-01-20', count: 290 },
  { date: '2026-01-21', count: 305 },
  { date: '2026-01-22', count: 340 },
  { date: '2026-01-23', count: 270 },
  { date: '2026-01-24', count: 320 },
  { date: '2026-01-25', count: 355 },
];

export const MOCK_ORG_RANKING: TokenUsageRankingEntry[] = MOCK_ORG_MEMBERS.map((member, i) => ({
  rank: i + 1,
  member,
  cost: parseFloat((34.9 - i * 0.8).toFixed(1)),
}));

export const MOCK_ORG_SUMMARY: TokenUsageSummary = {
  total_cost: 118.6,
  status: 'normal',
};

/* ─── 제한 해제 요청 ─── */

export const MOCK_LIMIT_RELEASE_REQUESTS: LimitReleaseRequest[] = [
  { id: 'lr-1', userId: '2', name: '직원20', email: 'user@example.com', team: '부서M', position: '팀원', cost: 754, requestedAmount: 50, reason: '긴급 프로젝트 마감 기한 임박', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-20T09:00:00Z' },
  { id: 'lr-2', userId: '3', name: '직원04', email: 'user@example.com', team: '부서B', position: '팀장', cost: 754, requestedAmount: 30, reason: '대규모 데이터 분석 작업 필요', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-20T10:30:00Z' },
  { id: 'lr-3', userId: '4', name: '직원10', email: 'user@example.com', team: '부서I', position: '팀원', cost: 754, requestedAmount: 754, reason: '분기 보고서 작성 지원', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-19T14:00:00Z' },
  { id: 'lr-4', userId: '5', name: '직원25', email: 'user@example.com', team: '부서F', position: '팀원', cost: 754, requestedAmount: 26, reason: '고객 미팅 자료 준비', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-19T11:00:00Z' },
  { id: 'lr-5', userId: '6', name: '직원28', email: 'user@example.com', team: '부서N', position: '팀원', cost: 754, requestedAmount: 130, reason: '신규 서비스 기획안 작성', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-18T16:00:00Z' },
  { id: 'lr-6', userId: '7', name: '직원29', email: 'user@example.com', team: '부서D', position: '팀장', cost: 754, requestedAmount: 150, reason: 'API 연동 테스트 진행', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-18T09:30:00Z' },
  { id: 'lr-7', userId: '8', name: '직원21', email: 'user@example.com', team: '부서G', position: '팀원', cost: 754, requestedAmount: 600, reason: '대규모 번역 작업 진행', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-17T13:00:00Z' },
  { id: 'lr-8', userId: '9', name: '직원18', email: 'user@example.com', team: '부서K', position: '팀원', cost: 754, requestedAmount: 3, reason: '간단한 문서 검토', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-17T10:00:00Z' },
  { id: 'lr-9', userId: '10', name: '직원22', email: 'user@example.com', team: '부서C', position: '팀원', cost: 754, requestedAmount: 5, reason: '이메일 초안 작성', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-16T15:00:00Z' },
  { id: 'lr-10', userId: '11', name: '직원02', email: 'user@example.com', team: '부서A', position: '팀장', cost: 754, requestedAmount: 5, reason: '프레젠테이션 자료 보완', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-16T09:00:00Z' },
  { id: 'lr-11', userId: '12', name: '직원15', email: 'user@example.com', team: '부서J', position: '팀원', cost: 320, requestedAmount: 45, reason: '마케팅 캠페인 콘텐츠 제작', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-15T14:30:00Z' },
  { id: 'lr-12', userId: '13', name: '직원27', email: 'user@example.com', team: '부서E', position: '팀원', cost: 890, requestedAmount: 200, reason: '코드 리뷰 및 리팩토링 지원', dailyLimit: 5, monthlyLimit: 90, requestedAt: '2026-02-15T11:00:00Z' },
];
