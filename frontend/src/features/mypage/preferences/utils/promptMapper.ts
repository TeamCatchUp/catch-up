import { ANSWER_OPTIONS, JOB_ROLE_OPTIONS } from '../constants/preferencesConfig';
import type { AnswerOption, JobRole } from '../types/preferencesModel';

/**
 * 프론트 label ↔ 백엔드 StrEnum 값 사이의 공백 차이를 정규화.
 * 프론트: "CS · 운영", 백엔드: "CS·운영" (가운데점 주변 공백 유무)
 */
function normalize(s: string): string {
  return s.replace(/\s*·\s*/g, '·').trim();
}

/* ── lookup map (모듈 스코프에서 1회 생성) ── */

const jobValueToLabel = new Map(JOB_ROLE_OPTIONS.map((o) => [o.value, o.label]));
const jobLabelToValue = new Map(JOB_ROLE_OPTIONS.map((o) => [normalize(o.label), o.value]));

const optionValueToLabel = new Map(ANSWER_OPTIONS.map((o) => [o.value, o.label]));
const optionLabelToValue = new Map(ANSWER_OPTIONS.map((o) => [normalize(o.label), o.value]));

/* ── JobRole 매핑 ── */

export function jobRoleToApi(value: JobRole | null): string | null {
  if (value === null) return null;
  const label = jobValueToLabel.get(value);
  if (label === undefined) return null;
  return normalize(label);
}

export function jobRoleFromApi(apiValue: string | null): JobRole | null {
  if (apiValue === null) return null;
  return jobLabelToValue.get(normalize(apiValue)) ?? null;
}

/* ── AnswerOption 매핑 ── */

export function optionsToApi(values: AnswerOption[]): string[] {
  return values
    .map((v) => optionValueToLabel.get(v))
    .filter((v): v is string => v !== undefined)
    .map(normalize);
}

export function optionsFromApi(apiValues: string[]): AnswerOption[] {
  return apiValues
    .map((v) => optionLabelToValue.get(normalize(v)))
    .filter((v): v is AnswerOption => v !== undefined);
}

/* ── null ↔ 빈 문자열 변환 ── */

export function nullToEmpty(value: string | null): string {
  return value ?? '';
}

export function emptyToNull(value: string): string | null {
  return value.trim() === '' ? null : value.trim();
}
