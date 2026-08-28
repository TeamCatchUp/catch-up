/** 자동화 커넥터 목록 API(GET /automations/credentials·targets) 응답. 여러 기능이 함께 쓴다. */
export type AutomationConnector = 'slack' | 'channel_talk';

export interface AutomationCredentialItem {
  connector: AutomationConnector;
  credential_id: number;
  display_name: string;
  external_id: string;
  external_name: string | null;
  is_configured: boolean;
  metadata: Record<string, unknown>;
}

export interface AutomationCredentialsResponse {
  connector: AutomationConnector;
  total_credentials: number;
  credentials: AutomationCredentialItem[];
}

export interface AutomationTargetItem {
  connector: AutomationConnector;
  credential_id: number | null;
  target_id: string;
  display_name: string;
  target_type: string;
  is_accessible: boolean;
  metadata: Record<string, unknown>;
}

export interface AutomationTargetsResponse {
  connector: AutomationConnector;
  credential_id: number | null;
  total_targets: number;
  targets: AutomationTargetItem[];
}
