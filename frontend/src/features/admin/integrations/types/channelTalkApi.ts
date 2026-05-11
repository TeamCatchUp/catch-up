// 백엔드 admin_api.py 응답 1:1 매칭 (snake_case)

// ─── Channel Credential ───

// POST /credentials(/validate) request
export interface ChannelTalkCredentialRequest {
  access_key: string;
  access_secret: string;
  webhook_token: string;
}

// POST /credentials/validate response
export interface ChannelTalkValidateResponse {
  status: 'validated';
  channel_id: string;
  channel_name: string;
  manager_id: string | null;
  manager_name: string | null;
  webhook_token_configured: boolean;
}

// POST /credentials response (upsert)
export interface ChannelTalkConnectResponse {
  installed: boolean;
  channel_id: string | null;
  channel_name: string | null;
  credential_last_verified_at: string | null;
  webhook_token_configured: boolean;
  status_reason: string | null;
  status: 'connected';
  message: string;
}

// ─── Document Space Credential ───

// POST /documents/credentials(/validate) request
export interface ChannelTalkDocumentCredentialRequest {
  access_key: string;
  access_secret: string;
  // 백엔드 ge=1, le=168. CHANNEL_TALK_SYNC_INTERVAL_HOURS 로 label→int 변환
  polling_cycle_hours: number;
}

// POST /documents/credentials/validate response
export interface ChannelTalkDocumentValidateResponse {
  status: 'validated';
  channel_id: string;
  space_id: string;
  space_name: string;
  association_status: string;
}

// POST /documents/credentials response (upsert)
export interface ChannelTalkDocumentConnectResponse {
  installed: boolean;
  channel_id: string | null;
  space_id: string | null;
  space_name: string | null;
  credential_last_verified_at: string | null;
  association_status: string | null;
  status_reason: string | null;
  status: 'connected';
  message: string;
}

// ─── Uninstall (DELETE) ───

// DELETE /credentials?channel_id=X
export interface ChannelTalkUninstallResponse {
  status: 'success' | 'not_found';
  message: string;
  installed: boolean;
}

// DELETE /documents/credentials?space_id=X (Channel과 동일 형태)
export type ChannelTalkDocumentUninstallResponse = ChannelTalkUninstallResponse;
