import { formatFullDate, formatRelativeDate } from '@/shared/utils/formatDate';

import type { QuestionLogItem } from '../types/questionLog';

const toItem = (id: string, sessionId: string, query: string, createdAt: string, isSaved = false): QuestionLogItem => {
  const rawDate = new Date(createdAt);
  return { id, sessionId, query, createdAt, rawDate, fullDate: formatFullDate(createdAt), relativeDate: formatRelativeDate(createdAt), isSaved };
};

const today = new Date();
const daysAgo = (n: number) => {
  const d = new Date(today);
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

export const MOCK_QUESTION_LOGS: QuestionLogItem[] = [
  toItem('ql-01', 's-01', '일본 시장 진출 전체 진행 상황 요약해줘', daysAgo(0)),
  toItem('ql-02', 's-02', '최근 고객 피드백 중 부정적 의견 요약', daysAgo(0), true),
  toItem('ql-03', 's-03', '부서F KPI 달성률 현황 알려줘', daysAgo(2)),
  toItem('ql-04', 's-04', '지난주 Sprint 회고 내용 정리', daysAgo(3)),
  toItem('ql-05', 's-05', 'Q1 매출 목표 대비 실적 비교', daysAgo(4), true),
  toItem('ql-06', 's-06', '신규 기능 출시 일정과 담당자 알려줘', daysAgo(5)),
  toItem('ql-07', 's-07', '경쟁사 B2B SaaS 가격 정책 비교', daysAgo(10)),
  toItem('ql-08', 's-08', '지난달 CS 인입량 추이 분석', daysAgo(12)),
  toItem('ql-09', 's-09', '채용 프로세스 개선안 브레인스토밍', daysAgo(15)),
  toItem('ql-10', 's-10', '연간 사업 계획서 초안 검토해줘', daysAgo(20), true),
  toItem('ql-11', 's-11', '팀 빌딩 이벤트 아이디어 추천', daysAgo(25)),
  toItem('ql-12', 's-12', '인프라 비용 절감 방안 정리', daysAgo(30)),
  toItem('ql-13', 's-13', '온보딩 프로세스 개선 제안서 작성', daysAgo(35)),
];
