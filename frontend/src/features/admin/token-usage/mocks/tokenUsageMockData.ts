import type {
  DailyTokenUsage,
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
