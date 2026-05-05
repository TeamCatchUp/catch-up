// ─── Channel Talk API Types (백엔드 admin_api.py 응답 1:1 매칭, snake_case) ───

// ─── Channel Credential ───

/** POST /api/v1/admin/connector/channel_talk/credentials(/validate) 요청 body */
export interface ChannelTalkCredentialRequest {
  access_key: string;
  access_secret: string;
  webhook_token: string;
}

/** POST /api/v1/admin/connector/channel_talk/credentials/validate 응답 */
export interface ChannelTalkValidateResponse {
  status: 'validated';
  channel_id: string;
  channel_name: string;
  manager_id: string | null;
  manager_name: string | null;
  webhook_token_configured: boolean;
}

/** POST /api/v1/admin/connector/channel_talk/credentials 응답 (upsert) */
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

/** POST /api/v1/admin/connector/channel_talk/documents/credentials(/validate) 요청 body */
export interface ChannelTalkDocumentCredentialRequest {
  access_key: string;
  access_secret: string;
}

/** POST /api/v1/admin/connector/channel_talk/documents/credentials/validate 응답 */
export interface ChannelTalkDocumentValidateResponse {
  status: 'validated';
  channel_id: string;
  space_id: string;
  space_name: string;
  association_status: string;
}

/** POST /api/v1/admin/connector/channel_talk/documents/credentials 응답 (upsert) */
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

/** DELETE /credentials?channel_id=X 응답 */
export interface ChannelTalkUninstallResponse {
  status: 'success' | 'not_found';
  message: string;
  installed: boolean;
}

/** DELETE /documents/credentials?space_id=X 응답 (Channel과 동일 형태) */
export type ChannelTalkDocumentUninstallResponse = ChannelTalkUninstallResponse;
