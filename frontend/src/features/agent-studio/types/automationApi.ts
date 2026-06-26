export type AutomationConnector = 'slack' | 'channel_talk';
export type InquiryAutomationStatus = 'draft' | 'active' | 'inactive';
export type InquiryAutomationMutableStatus = Extract<InquiryAutomationStatus, 'active' | 'inactive'>;

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

export interface InquiryAutomationItem {
  agent_spec_id: number;
  status: InquiryAutomationStatus;
  title?: string | null;
  channel_talk_credential_id: number;
  slack_channel_id: string;
  slack_credential_id: number;
  guide_instruction: string | null;
  quiet_period_seconds: number | null;
  trigger_id: number | null;
  author_name?: string | null;
  updated_at?: string | null;
  author_profile_image_url?: string | null;
}

export interface InquiryAutomationUpdateRequest {
  status: InquiryAutomationMutableStatus;
}

export interface InquiryAutomationPublishRequest {
  channel_talk_credential_id: number;
  quiet_period_seconds: number;
  slack_channel: {
    credential_id: number;
    channel_id: string;
    channel_name?: string;
  };
  guide_instruction?: string | null;
}

export interface InquiryAutomationPatchRequest {
  channel_talk_credential_id?: number | null;
  quiet_period_seconds?: number | null;
  slack_channel?: {
    credential_id: number;
    channel_id: string;
    channel_name?: string;
  } | null;
  guide_instruction?: string | null;
}

export interface InquiryAutomationPublishResponse {
  agent_spec_id: number;
  trigger_id: number;
  status: InquiryAutomationStatus;
  channel_talk_channel_id: string;
  channel_talk_channel_name: string;
  quiet_period_seconds: number;
  slack_channel_id: string;
  start_event_type: string;
  reset_event_types: string[];
}
