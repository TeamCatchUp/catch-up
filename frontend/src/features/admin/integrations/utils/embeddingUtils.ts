import IconSpace from '@/public/icons/icon/space.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconGithubLogo from '@/public/icons/logo/GitHub.svg';

import type { SyncConnector } from '../types/syncModel';

/** 서비스별 리소스 아이템 아이콘 */
export const RESOURCE_ICONS: Record<SyncConnector, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  jira: IconSpace,
  github: IconGithubLogo,
  slack: IconTag,
  confluence: IconSpace,
  // 채널톡은 채널(채팅) + 스페이스(문서) 모두 sync target이지만, 메인은 채널이므로 Slack과 동일한 채널 아이콘 사용.
  channel_talk: IconTag,
};

/**
 * 날짜 문자열 → "2026.03.18" 포맷.
 *
 * 임베딩된 대상 표의 "데이터 범위"와 커넥터 요약 카드가 쓰는 날짜 형식이다
 * (Figma `17169:75787` — `2000.00.00`). 리디자인 전에는 "2026. 3. 6."처럼
 * 공백이 들어가고 0을 안 채웠는데 신규 디자인과 달라 맞췄다.
 */
export const formatEmbeddingDate = (dateStr: string | null): string => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}.${month}.${day}`;
};

/**
 * 임베딩 데이터 범위 → "2026.03.06 - 2026.05.04".
 * 구분자는 하이픈이다(Figma `17169:75787`은 `2000.00.00 - 2000.00.00`).
 *
 * 한쪽만 있으면 그 날짜만 낸다 — 예전에는 " ~ 2026. 5. 4."처럼 구분자가
 * 앞에 남았다. 둘 다 없으면 "-".
 */
export const formatEmbeddingRange = (oldest: string | null, latest: string | null): string => {
  const from = formatEmbeddingDate(oldest);
  const to = formatEmbeddingDate(latest);
  if (!from && !to) return '-';
  if (!from) return to;
  if (!to) return from;
  return `${from} - ${to}`;
};

/**
 * 날짜 문자열 → "2026.03.18 09:52 PM" 포맷. "YYYY-MM-DD" 및 ISO datetime 모두 지원.
 *
 * 임베딩 현황 표의 "실행 시각" 형식이다(Figma `17169:75993` — `2026.03.18 00:00 PM`).
 * 리디자인 전에는 요일 `(수)`이 들어갔는데 신규 디자인에 없어 뺐다.
 */
export const formatHistoryDate = (dateStr: string): string => {
  if (!dateStr) return '';
  const format = (d: Date): string => {
    const y = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = d.getHours();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const h12 = String(hours % 12 || 12).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${y}.${month}.${day} ${h12}:${minutes} ${ampm}`;
  };
  // "YYYY-MM-DD" 형태: 직접 파싱 (타임존 변환 방지)
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, d] = dateStr.split('-').map(Number);
    return format(new Date(y, m - 1, d));
  }
  // ISO datetime: Date 파싱 후 로컬 시간 사용
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return format(d);
};
