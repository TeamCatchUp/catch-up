// ─── Connection Status API Types (백엔드 connector_core/ports/connection_status.py 1:1 매칭, snake_case) ───

import type { SyncConnector } from './syncModel';

/**
 * canonical endpoint `GET /api/v1/integrations/{vendor}/connection-status`의 vendor.
 *
 * SyncConnector(github/slack/jira/confluence/channel_talk)에 atlassian이 추가된 형태.
 * atlassian은 jira/confluence가 공유하는 OAuth 단위 — 클라이언트는 atlassian 1회 호출 후
 * `filterAtlassianScope`로 jira/confluence를 분리한다.
 */
export type ConnectorVendor = SyncConnector | 'atlassian';

export type ConnectionType = 'oauth_token' | 'installation' | 'credential';

interface ConnectionStatusItemBase<TMeta> {
  id: string;
  name: string | null;
  connected_at: string | null;
  metadata: TMeta;
}

// ─── Vendor-specific metadata ───

export interface GithubConnectionMetadata {
  account_type: string;
  account_id: number;
  repository_selection: string;
  suspended_at: string | null;
}

export interface SlackConnectionMetadata {
  bot_user_id: string;
  scopes: string[];
}

export interface AtlassianConnectionMetadata {
  atlassian_account_id: string;
  site_url: string;
  scopes: string[];
}

export type ChannelTalkConnectionMetadata =
  | {
      credential_type: 'channel';
      last_verified_at: string | null;
      webhook_token_configured: boolean;
    }
  | {
      credential_type: 'document_space';
      channel_id: string;
      association_status: string;
      last_verified_at: string | null;
      polling_cycle_hours: number;
    };

// ─── Discriminated union — vendor 좁힘으로 metadata 자동 결정 ───

interface ConnectionStatusBase {
  connected: boolean;
  count: number;
}

export type ConnectionStatusResponse =
  | (ConnectionStatusBase & {
      vendor: 'github';
      connection_type: 'installation';
      items: ConnectionStatusItemBase<GithubConnectionMetadata>[];
    })
  | (ConnectionStatusBase & {
      vendor: 'slack';
      connection_type: 'oauth_token';
      items: ConnectionStatusItemBase<SlackConnectionMetadata>[];
    })
  | (ConnectionStatusBase & {
      vendor: 'atlassian' | 'jira' | 'confluence';
      connection_type: 'oauth_token';
      items: ConnectionStatusItemBase<AtlassianConnectionMetadata>[];
    })
  | (ConnectionStatusBase & {
      vendor: 'channel_talk';
      connection_type: 'credential';
      items: ConnectionStatusItemBase<ChannelTalkConnectionMetadata>[];
    });

// ─── Vendor별 응답 추출 alias ───

export type AtlassianConnectionStatusResponse = Extract<
  ConnectionStatusResponse,
  { vendor: 'atlassian' | 'jira' | 'confluence' }
>;
export type ChannelTalkConnectionStatusResponse = Extract<ConnectionStatusResponse, { vendor: 'channel_talk' }>;
