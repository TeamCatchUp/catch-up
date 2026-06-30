import type { AutomationCredentialItem, AutomationTargetItem } from '../types/automationApi';

interface AreInquiryAutomationSettingsSelectedOptions {
  channelTalkTarget?: AutomationTargetItem;
  slackCredential?: AutomationCredentialItem;
  slackTarget?: AutomationTargetItem;
}

interface CanSubmitInquiryAutomationSettingsOptions {
  hasEditChannelTalkTarget: boolean;
  hasSelectedAutomationSettings: boolean;
  isDetailLoaded: boolean;
  isEditable: boolean;
  isEditMode: boolean;
  isPending: boolean;
}

export function areInquiryAutomationSettingsSelected({
  channelTalkTarget,
  slackCredential,
  slackTarget,
}: AreInquiryAutomationSettingsSelectedOptions): boolean {
  return (
    channelTalkTarget?.credential_id !== null &&
    channelTalkTarget?.credential_id !== undefined &&
    channelTalkTarget.is_accessible &&
    slackCredential?.is_configured === true &&
    slackTarget?.is_accessible === true
  );
}

export function canSubmitInquiryAutomationSettings({
  hasEditChannelTalkTarget,
  hasSelectedAutomationSettings,
  isDetailLoaded,
  isEditable,
  isEditMode,
  isPending,
}: CanSubmitInquiryAutomationSettingsOptions): boolean {
  if (isPending || !hasSelectedAutomationSettings) {
    return false;
  }

  if (!isEditMode) {
    return true;
  }

  return isDetailLoaded && isEditable && hasEditChannelTalkTarget;
}
