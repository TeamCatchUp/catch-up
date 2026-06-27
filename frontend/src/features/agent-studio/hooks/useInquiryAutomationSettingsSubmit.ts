'use client';

import { useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { AGENT_EDITOR_SETTINGS_MESSAGES } from '../constants/agentEditorSettingsMessages';
import { inquiryAutomationsMutations } from '../queries/inquiryAutomations.mutations';
import { inquiryAutomationsQueries } from '../queries/inquiryAutomations.queries';
import type { AutomationCredentialItem, AutomationTargetItem, InquiryAutomationItem } from '../types/automationApi';
import {
  buildInquiryAutomationSettingsPatchPayload,
  buildInquiryAutomationSettingsPayload,
} from '../utils/buildInquiryAutomationSettingsPayload';
import { canSubmitInquiryAutomationSettings } from '../utils/validateInquiryAutomationSettings';

interface UseInquiryAutomationSettingsSubmitOptions {
  automationDetail?: InquiryAutomationItem;
  defaultQuietPeriodSeconds: number;
  hasAutomationDetailLoadError: boolean;
  hasEditChannelTalkTarget: boolean;
  hasSelectedAutomationSettings: boolean;
  isAutomationDetailLoaded: boolean;
  isEditMode: boolean;
  isEditable: boolean;
  quietPeriodValue: string;
  resolvedAgentSpecId?: number;
  selectedChannelTalkTarget?: AutomationTargetItem;
  selectedSlackCredential?: AutomationCredentialItem;
  selectedSlackCredentialId?: number;
  selectedSlackTarget?: AutomationTargetItem;
}

export function useInquiryAutomationSettingsSubmit({
  automationDetail,
  defaultQuietPeriodSeconds,
  hasAutomationDetailLoadError,
  hasEditChannelTalkTarget,
  hasSelectedAutomationSettings,
  isAutomationDetailLoaded,
  isEditMode,
  isEditable,
  quietPeriodValue,
  resolvedAgentSpecId,
  selectedChannelTalkTarget,
  selectedSlackCredential,
  selectedSlackCredentialId,
  selectedSlackTarget,
}: UseInquiryAutomationSettingsSubmitOptions) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const isSubmitInFlightRef = useRef(false);

  const publishMutation = useMutation({
    ...inquiryAutomationsMutations.publish(),
    onSuccess: () => {
      router.push('/agent-studio');
    },
    onError: () => {
      toast.error(AGENT_EDITOR_SETTINGS_MESSAGES.publishError);
    },
    onSettled: () => {
      isSubmitInFlightRef.current = false;
    },
  });

  const patchSettingsMutation = useMutation({
    ...inquiryAutomationsMutations.patchSettings(),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: inquiryAutomationsQueries.detailKey(variables.agentSpecId) });
      router.push('/agent-studio');
    },
    onError: () => {
      toast.error(AGENT_EDITOR_SETTINGS_MESSAGES.patchError);
    },
    onSettled: () => {
      isSubmitInFlightRef.current = false;
    },
  });

  const canSubmit = canSubmitInquiryAutomationSettings({
    hasEditChannelTalkTarget,
    hasSelectedAutomationSettings,
    isDetailLoaded: isAutomationDetailLoaded,
    isEditable,
    isEditMode,
    isPending: isEditMode ? patchSettingsMutation.isPending : publishMutation.isPending,
  });

  const handleSubmit = () => {
    if (
      publishMutation.isPending ||
      patchSettingsMutation.isPending ||
      isSubmitInFlightRef.current ||
      !canSubmit
    ) {
      return;
    }

    const payload = buildInquiryAutomationSettingsPayload({
      channelTalkTarget: selectedChannelTalkTarget,
      quietPeriodValue,
      slackCredential: selectedSlackCredential,
      slackCredentialId: selectedSlackCredentialId,
      slackTarget: selectedSlackTarget,
    });
    if (payload === null) return;

    isSubmitInFlightRef.current = true;

    if (isEditMode) {
      if (resolvedAgentSpecId === undefined) {
        isSubmitInFlightRef.current = false;
        return;
      }
      const patchPayload = buildInquiryAutomationSettingsPatchPayload({
        automationDetail,
        defaultQuietPeriodSeconds,
        settingsPayload: payload,
      });
      if (patchPayload === null) {
        isSubmitInFlightRef.current = false;
        return;
      }

      patchSettingsMutation.mutate({ agentSpecId: resolvedAgentSpecId, body: patchPayload });
      return;
    }

    publishMutation.mutate(payload);
  };

  const loadErrorMessage = hasAutomationDetailLoadError ? AGENT_EDITOR_SETTINGS_MESSAGES.loadError : null;

  useEffect(() => {
    if (loadErrorMessage) {
      toast.error(loadErrorMessage);
    }
  }, [loadErrorMessage]);

  return {
    canSubmit,
    handleSubmit,
  };
}
