'use client';

import { useState } from 'react';

import { useAgentEditorSettingsSelects } from './useAgentEditorSettingsSelects';
import { useInquiryAutomationSettingsSubmit } from './useInquiryAutomationSettingsSubmit';

interface UseAgentEditorSettingsFormOptions {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

export function useAgentEditorSettingsForm({ mode = 'create', agentSpecId }: UseAgentEditorSettingsFormOptions = {}) {
  const isEditMode = mode === 'edit';
  const resolvedAgentSpecId = isEditMode ? agentSpecId : undefined;
  const [instructionOverride, setInstructionOverride] = useState<string | null>(null);

  const settingsSelects = useAgentEditorSettingsSelects({
    isEditMode,
    resolvedAgentSpecId,
  });
  const instruction =
    instructionOverride ??
    (isEditMode && settingsSelects.automationDetail !== undefined
      ? (settingsSelects.automationDetail.guide_instruction ?? '')
      : '');

  const { canSubmit, handleSubmit } = useInquiryAutomationSettingsSubmit({
    automationDetail: settingsSelects.automationDetail,
    defaultQuietPeriodSeconds: settingsSelects.defaultQuietPeriodSeconds,
    guideInstruction: instruction,
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
    instruction,
    isReadOnly: settingsSelects.isEditReadOnly,
    quietPeriodSelect: settingsSelects.quietPeriodSelect,
    setInstruction: setInstructionOverride,
    slackChannelSelect: settingsSelects.slackChannelSelect,
    slackCredentialSelect: settingsSelects.slackCredentialSelect,
  };
}
