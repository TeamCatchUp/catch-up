import type { ComponentType, SVGProps } from 'react';

import IconHistory from '@/public/icons/icon/history.svg';
import IconPerson from '@/public/icons/icon/person2.svg';
import IconScreen from '@/public/icons/icon/screen.svg';
import IconStacks from '@/public/icons/icon/stacks.svg';
import IconTag from '@/public/icons/icon/tag2.svg';
import IconTarget from '@/public/icons/icon/target.svg';

import type { AnswerOption, JobRole, ThemeMode } from '../types/preferencesModel';

/* ── 직무 선택 ── */

export const JOB_ROLE_OPTIONS: { value: JobRole; label: string }[] = [
  { value: 'pm', label: '기획자 (PM)' },
  { value: 'developer', label: '개발자' },
  { value: 'designer', label: '디자이너' },
  { value: 'cs_ops', label: 'CS · 운영' },
  { value: 'business_strategy', label: '경영 · 전략' },
  { value: 'sales', label: '세일즈' },
  { value: 'custom', label: '직접 입력' },
];

/* ── 답변 옵션 ── */

export const ANSWER_OPTIONS: {
  value: AnswerOption;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  tooltip: string;
}[] = [
  { value: 'glossary', label: '용어 설명 포함', icon: IconTag, tooltip: '전문 용어를 자동으로 설명해드려요' },
  {
    value: 'background',
    label: '작업 배경 설명',
    icon: IconHistory,
    tooltip: '이 작업이 왜 시작됐는지 먼저 설명해드려요',
  },
  {
    value: 'assignee',
    label: '담당자 자동 표시',
    icon: IconPerson,
    tooltip: '실질 담당자를 자동으로 찾아 답변 하단에 표시해드려요',
  },
  {
    value: 'similar_cases',
    label: '유사 사례 첨부',
    icon: IconStacks,
    tooltip: '비슷한 과거 이슈를 자동으로 연결해드려요',
  },
  {
    value: 'impact_scope',
    label: '구현 영향 범위 명시',
    icon: IconTarget,
    tooltip: '영향받는 API·컴포넌트 범위를 명세해드려요',
  },
  {
    value: 'ux_impact',
    label: '화면 · UX 영향 명시',
    icon: IconScreen,
    tooltip: '화면·인터랙션에 미치는 영향을 명시해드려요',
  },
];

/* ── 화면 모드 ── */

export const THEME_OPTIONS: { value: ThemeMode; label: string }[] = [
  { value: 'system', label: '시스템' },
  { value: 'light', label: '라이트' },
  { value: 'dark', label: '다크' },
];

/* ── 글자수 제한 ── */

export const MAX_JOB_TEXT_LENGTH = 50;
export const MAX_JOB_DESCRIPTION_LENGTH = 200;
export const MAX_PROMPT_LENGTH = 500;
