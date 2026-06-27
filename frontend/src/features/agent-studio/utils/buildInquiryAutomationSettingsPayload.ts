import type {
  AutomationCredentialItem,
  AutomationTargetItem,
  InquiryAutomationItem,
  InquiryAutomationPatchRequest,
  InquiryAutomationPublishRequest,
} from '../types/automationApi';
import { areInquiryAutomationSettingsSelected } from './validateInquiryAutomationSettings';

interface BuildInquiryAutomationSettingsPayloadOptions {
  channelTalkTarget?: AutomationTargetItem;
  guideInstruction: string;
  quietPeriodValue: string;
  slackCredential?: AutomationCredentialItem;
  slackCredentialId?: number;
  slackTarget?: AutomationTargetItem;
}

interface BuildInquiryAutomationSettingsPatchPayloadOptions {
  automationDetail?: InquiryAutomationItem;
  defaultQuietPeriodSeconds: number;
  settingsPayload: InquiryAutomationPublishRequest;
}

function normalizeGuideInstruction(value: string | null | undefined): string | null {
  const trimmedValue = value?.trim() ?? '';

  return trimmedValue.length > 0 ? trimmedValue : null;
}

export function buildInquiryAutomationSettingsPayload({
  channelTalkTarget,
  guideInstruction,
  quietPeriodValue,
  slackCredential,
  slackCredentialId,
  slackTarget,
}: BuildInquiryAutomationSettingsPayloadOptions): InquiryAutomationPublishRequest | null {
  const channelTalkCredentialId = channelTalkTarget?.credential_id;

  if (
    channelTalkCredentialId === null ||
    channelTalkCredentialId === undefined ||
    slackCredentialId === undefined ||
    slackTarget === undefined ||
    !areInquiryAutomationSettingsSelected({ channelTalkTarget, slackCredential, slackTarget })
  ) {
    return null;
  }

  return {
    channel_talk_credential_id: channelTalkCredentialId,
    guide_instruction: normalizeGuideInstruction(guideInstruction),
    quiet_period_seconds: Number(quietPeriodValue),
    slack_channel: {
      credential_id: slackCredentialId,
      channel_id: slackTarget.target_id,
      channel_name: slackTarget.display_name,
    },
  };
}

export function buildInquiryAutomationSettingsPatchPayload({
  automationDetail,
  defaultQuietPeriodSeconds,
  settingsPayload,
}: BuildInquiryAutomationSettingsPatchPayloadOptions): InquiryAutomationPatchRequest | null {
  if (automationDetail === undefined) return null;

  const patchPayload: InquiryAutomationPatchRequest = {};

  if (settingsPayload.channel_talk_credential_id !== automationDetail.channel_talk_credential_id) {
    patchPayload.channel_talk_credential_id = settingsPayload.channel_talk_credential_id;
  }

  if (settingsPayload.quiet_period_seconds !== (automationDetail.quiet_period_seconds ?? defaultQuietPeriodSeconds)) {
    patchPayload.quiet_period_seconds = settingsPayload.quiet_period_seconds;
  }

  if (
    settingsPayload.slack_channel.credential_id !== automationDetail.slack_credential_id ||
    settingsPayload.slack_channel.channel_id !== automationDetail.slack_channel_id
  ) {
    patchPayload.slack_channel = settingsPayload.slack_channel;
  }

  if (settingsPayload.guide_instruction !== normalizeGuideInstruction(automationDetail.guide_instruction)) {
    patchPayload.guide_instruction = settingsPayload.guide_instruction ?? null;
  }

  return patchPayload;
}
