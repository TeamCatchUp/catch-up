import type {
  DailyTokenUsage,
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
  { id: '1', name: '팀원G', team: '사업개발팀', position: 'PM', role: '루트 어드민', tokenEnabled: true, cost: 34.1 },
  { id: '2', name: '직원20', team: '부서O', position: '디자이너', role: '일반', tokenEnabled: false, cost: 12.5 },
  { id: '3', name: '직원04', team: '부서O', position: '개발자', role: '일반', tokenEnabled: true, cost: 28.3 },
  { id: '4', name: '박지현', team: '부서O', position: '기획자', role: '일반', tokenEnabled: true, cost: 9.7 },
  { id: '5', name: '최영호', team: '부서O', position: 'PM', role: '일반', tokenEnabled: true, cost: 22.0 },
  { id: '6', name: '정수진', team: '부서O', position: '디자이너', role: '일반', tokenEnabled: false, cost: 5.2 },
  { id: '7', name: '한동훈', team: '부서O', position: '개발자', role: '일반', tokenEnabled: true, cost: 18.6 },
  { id: '8', name: '오세린', team: '부서O', position: '기획자', role: '일반', tokenEnabled: true, cost: 7.4 },
  { id: '9', name: '윤재석', team: '부서O', position: '개발자', role: '일반', tokenEnabled: true, cost: 15.1 },
  { id: '10', name: '송하나', team: '부서O', position: '디자이너', role: '일반', tokenEnabled: true, cost: 3.8 },
  { id: '11', name: '임도현', team: '부서O', position: 'PM', role: '일반', tokenEnabled: true, cost: 11.9 },
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
