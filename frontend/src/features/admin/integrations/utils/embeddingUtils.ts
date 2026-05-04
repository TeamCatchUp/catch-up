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

/** 날짜 문자열 → "2026.03.18 (수) 09:52 PM" 포맷. "YYYY-MM-DD" 및 ISO datetime 모두 지원. */
export const formatHistoryDate = (dateStr: string): string => {
  if (!dateStr) return '';
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const format = (d: Date): string => {
    const y = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = d.getHours();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const h12 = String(hours % 12 || 12).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${y}.${month}.${day} (${dayNames[d.getDay()]}) ${h12}:${minutes} ${ampm}`;
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
