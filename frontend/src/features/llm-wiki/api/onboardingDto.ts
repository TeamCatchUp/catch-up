/**
 * 온보딩 제출 API의 서버 DTO. 필드는 계약 그대로 snake_case다.
 * 채널 생성과 수집 설정 저장은 서로 다른 라우터라 한 요청으로 묶이지 않는다.
 */

/** 화면은 단일 선택이지만 서버는 배열을 받는다 — 1원소 배열로 보낸다 */
export interface WikiChannelOnboardingRequest {
  name: string;
  domain_preset: string;
  purpose_presets: string[];
  kinds: string[];
  style_preset: string;
}

/** 응답에는 정의·자동 생성 폴더도 실리지만 온보딩 화면은 소비하지 않는다 */
export interface WikiChannelOnboardingDto {
  id: string;
  name: string;
}

/** execution_anchor_at은 타임존이 필수고, 시작이 아니라 실행 위상이다 */
export interface KnowledgeMaintenanceSettingRequest {
  enabled: boolean;
  interval_minutes: number;
  execution_anchor_at: string;
}

export interface KnowledgeMaintenanceSettingDto {
  credential_id: number;
  enabled: boolean;
  interval_minutes: number;
  execution_anchor_at: string;
}
