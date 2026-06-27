'use client';

import { useAgentEditorSettingsSelects } from './useAgentEditorSettingsSelects';
import { useInquiryAutomationSettingsSubmit } from './useInquiryAutomationSettingsSubmit';

interface UseAgentEditorSettingsFormOptions {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

export function useAgentEditorSettingsForm({ mode = 'create', agentSpecId }: UseAgentEditorSettingsFormOptions = {}) {
  const isEditMode = mode === 'edit';
  const resolvedAgentSpecId = isEditMode ? agentSpecId : undefined;

  const settingsSelects = useAgentEditorSettingsSelects({
    isEditMode,
    resolvedAgentSpecId,
  });

  const { canSubmit, handleSubmit } = useInquiryAutomationSettingsSubmit({
    automationDetail: settingsSelects.automationDetail,
    defaultQuietPeriodSeconds: settingsSelects.defaultQuietPeriodSeconds,
    hasAutomationDetailLoadError: settingsSelects.hasAutomationDetailLoadError,
    hasEditChannelTalkTarget: settingsSelects.hasEditChannelTalkTarget,
    hasSelectedAutomationSettings: settingsSelects.hasSelectedAutomationSettings,
    isAutomationDetailLoaded: settingsSelects.isAutomationDetailLoaded,
    isEditable: settingsSelects.automationDetail?.is_editable === true,
    isEditMode,
    quietPeriodValue: settingsSelects.quietPeriodValue,
    resolvedAgentSpecId,
    selectedChannelTalkTarget: settingsSelects.selectedChannelTalkTarget,
    selectedSlackCredential: settingsSelects.selectedSlackCredential,
    selectedSlackCredentialId: settingsSelects.selectedSlackCredentialId,
    selectedSlackTarget: settingsSelects.selectedSlackTarget,
  });

  return {
    canSubmit,
    channelTalkSelect: settingsSelects.channelTalkSelect,
    handleSubmit,
    isReadOnly: settingsSelects.isEditReadOnly,
    quietPeriodSelect: settingsSelects.quietPeriodSelect,
    slackChannelSelect: settingsSelects.slackChannelSelect,
    slackCredentialSelect: settingsSelects.slackCredentialSelect,
  };
}
