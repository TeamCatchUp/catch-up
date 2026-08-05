/**
 * 이용자 매핑 화면 모델.
 * 백엔드 응답(`userSourceMappingApi.ts`)과 분리한 화면용 타입 — 어느 필드로
 * 채울지는 배선 단계에서 정한다. Confluence는 백엔드가 atlassian으로 합쳐
 * 응답하므로(스키마 주석) 화면 커넥터도 4종이다.
 */
export type MappingSource = 'atlassian' | 'github' | 'slack' | 'channel_talk';

export const MAPPING_SOURCES: readonly MappingSource[] = ['atlassian', 'github', 'slack', 'channel_talk'];

/** 표 헤더 라벨 — Figma `17060:75364` 그대로 */
export const MAPPING_SOURCE_LABELS: Record<MappingSource, string> = {
  atlassian: 'Atlassian',
  github: 'Github',
  slack: 'Slack',
  channel_talk: '채널톡',
};

export interface MappingAccount {
  name: string;
  /** 이메일·아이디 등 식별자 — 2줄째 */
  identifier: string;
  picture?: string | null;
}

/** 셀 값: 계정 / 미사용 선언 / 미연동(빈 칸) */
export type MappingCellValue = MappingAccount | 'unused' | null;

export interface UserMappingRow {
  id: string;
  user: { name: string; picture?: string | null };
  /** 전 커넥터 연동 여부 — 좌측 상태 점 (녹/적) */
  fullyMapped: boolean;
  accounts: Partial<Record<MappingSource, MappingCellValue>>;
}
