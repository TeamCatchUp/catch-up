'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { AGENT_EDITOR_SETTINGS_MESSAGES } from '../constants/agentEditorSettingsMessages';
import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../fixtures/agentStudioFixtures';
import { automationCredentialsQueries } from '../queries/automationCredentials.queries';
import { inquiryAutomationsMutations } from '../queries/inquiryAutomations.mutations';
import { inquiryAutomationsQueries } from '../queries/inquiryAutomations.queries';
import type { AgentStudioSelectItem } from '../types/agentStudioModel';
import {
  buildInquiryAutomationSettingsPatchPayload,
  buildInquiryAutomationSettingsPayload,
} from '../utils/buildInquiryAutomationSettingsPayload';
import { mapAutomationCredentialToSelectItem, mapAutomationTargetToSelectItem } from '../utils/mapAutomationSelectItems';
import {
  areInquiryAutomationSettingsSelected,
  canSubmitInquiryAutomationSettings,
} from '../utils/validateInquiryAutomationSettings';

const EMPTY_SELECT_ITEMS: readonly AgentStudioSelectItem[] = [];
const DEFAULT_QUIET_PERIOD_SECONDS = AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions[0]?.value ?? '60';

interface UseAgentEditorSettingsFormOptions {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

export function useAgentEditorSettingsForm({ mode = 'create', agentSpecId }: UseAgentEditorSettingsFormOptions = {}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const isEditMode = mode === 'edit';
  const resolvedAgentSpecId = isEditMode ? agentSpecId : undefined;
  const isSubmitInFlightRef = useRef(false);
  const [channelTalkTargetId, setChannelTalkTargetId] = useState('');
  const [quietPeriodSeconds, setQuietPeriodSeconds] = useState('');
  const [slackCredentialId, setSlackCredentialId] = useState('');
  const [slackChannelId, setSlackChannelId] = useState('');

  const slackCredentialsQuery = useQuery(automationCredentialsQueries.credentials('slack'));
  const channelTalkTargetsQuery = useQuery(automationCredentialsQueries.targets('channel_talk'));
  const automationDetailQuery = useQuery({
    ...inquiryAutomationsQueries.detail(resolvedAgentSpecId ?? 0),
    enabled: isEditMode && resolvedAgentSpecId !== undefined,
  });
  const automationDetail = automationDetailQuery.data;

  const channelTalkTargetItems = useMemo(
    () => channelTalkTargetsQuery.data?.targets.map(mapAutomationTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [channelTalkTargetsQuery.data?.targets],
  );
  const slackCredentialItems = useMemo(
    () => slackCredentialsQuery.data?.credentials.map(mapAutomationCredentialToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [slackCredentialsQuery.data?.credentials],
  );
  const editChannelTalkTarget = useMemo(
    () =>
      isEditMode && automationDetail !== undefined
        ? channelTalkTargetsQuery.data?.targets.find(
            (target) => target.credential_id === automationDetail.channel_talk_credential_id,
          )
        : undefined,
    [automationDetail, channelTalkTargetsQuery.data?.targets, isEditMode],
  );
  const channelTalkTargetValue = channelTalkTargetId || editChannelTalkTarget?.target_id || '';
  const quietPeriodValue =
    quietPeriodSeconds ||
    (isEditMode && automationDetail !== undefined
      ? String(automationDetail.quiet_period_seconds ?? DEFAULT_QUIET_PERIOD_SECONDS)
      : DEFAULT_QUIET_PERIOD_SECONDS);
  const autoSlackCredentialId =
    slackCredentialItems.length === 1 && slackCredentialItems[0]?.disabled !== true
      ? (slackCredentialItems[0]?.value ?? '')
      : '';
  const editSlackCredentialId =
    isEditMode && automationDetail !== undefined ? String(automationDetail.slack_credential_id) : '';
  const slackCredentialValue = slackCredentialId || editSlackCredentialId || autoSlackCredentialId;
  const selectedSlackCredentialId = slackCredentialValue === '' ? undefined : Number(slackCredentialValue);
  const slackTargetsQuery = useQuery(automationCredentialsQueries.targets('slack', selectedSlackCredentialId));
  const slackChannelValue =
    slackChannelId || (isEditMode && automationDetail !== undefined ? automationDetail.slack_channel_id : '');
  const isEditReadOnly = isEditMode && automationDetail?.is_editable === false;

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

  const slackChannelItems = useMemo(
    () => slackTargetsQuery.data?.targets.map(mapAutomationTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [slackTargetsQuery.data?.targets],
  );
  const selectedChannelTalkTarget = useMemo(
    () => channelTalkTargetsQuery.data?.targets.find((target) => target.target_id === channelTalkTargetValue),
    [channelTalkTargetValue, channelTalkTargetsQuery.data?.targets],
  );
  const selectedSlackCredential = useMemo(
    () =>
      selectedSlackCredentialId === undefined
        ? undefined
        : slackCredentialsQuery.data?.credentials.find(
            (credential) => credential.credential_id === selectedSlackCredentialId,
          ),
    [selectedSlackCredentialId, slackCredentialsQuery.data?.credentials],
  );
  const selectedSlackTarget = useMemo(
    () => slackTargetsQuery.data?.targets.find((target) => target.target_id === slackChannelValue),
    [slackChannelValue, slackTargetsQuery.data?.targets],
  );

  const channelTalkPlaceholder = channelTalkTargetsQuery.isError
    ? AGENT_EDITOR_SETTINGS_MESSAGES.channelTalkTargetsLoadError
    : channelTalkTargetsQuery.isSuccess && channelTalkTargetItems.length === 0
      ? AGENT_EDITOR_SETTINGS_MESSAGES.emptySelectItems
      : AGENT_STUDIO_SETTINGS_FIXTURE.channelTalkChannelLabel;
  const slackCredentialPlaceholder = slackCredentialsQuery.isError
    ? AGENT_EDITOR_SETTINGS_MESSAGES.slackCredentialsLoadError
    : slackCredentialsQuery.isSuccess && slackCredentialItems.length === 0
      ? AGENT_EDITOR_SETTINGS_MESSAGES.emptySelectItems
      : AGENT_STUDIO_SETTINGS_FIXTURE.slackWorkspaceName;
  const slackChannelPlaceholder = slackTargetsQuery.isError
    ? AGENT_EDITOR_SETTINGS_MESSAGES.slackTargetsLoadError
    : selectedSlackCredentialId !== undefined && slackTargetsQuery.isSuccess && slackChannelItems.length === 0
      ? AGENT_EDITOR_SETTINGS_MESSAGES.emptySelectItems
      : AGENT_STUDIO_SETTINGS_FIXTURE.slackChannelLabel;
  const hasSelectedAutomationSettings = areInquiryAutomationSettingsSelected({
    channelTalkTarget: selectedChannelTalkTarget,
    slackCredential: selectedSlackCredential,
    slackTarget: selectedSlackTarget,
  });
  const canSubmit = canSubmitInquiryAutomationSettings({
    hasEditChannelTalkTarget: editChannelTalkTarget !== undefined,
    hasSelectedAutomationSettings,
    isDetailLoaded: automationDetailQuery.isSuccess,
    isEditable: automationDetail?.is_editable === true,
    isEditMode,
    isPending: isEditMode ? patchSettingsMutation.isPending : publishMutation.isPending,
  });

  const handleSlackCredentialChange = (value: string) => {
    setSlackCredentialId(value);
    setSlackChannelId('');
  };

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
        defaultQuietPeriodSeconds: Number(DEFAULT_QUIET_PERIOD_SECONDS),
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

  const loadErrorMessage = isEditMode && automationDetailQuery.isError ? AGENT_EDITOR_SETTINGS_MESSAGES.loadError : null;

  useEffect(() => {
    if (loadErrorMessage) {
      toast.error(loadErrorMessage);
    }
  }, [loadErrorMessage]);

  return {
    canSubmit,
    channelTalkSelect: {
      disabled:
        isEditReadOnly ||
        channelTalkTargetsQuery.isLoading || channelTalkTargetsQuery.isError || channelTalkTargetItems.length === 0,
      items: channelTalkTargetItems,
      onChange: setChannelTalkTargetId,
      placeholder: channelTalkPlaceholder,
      value: channelTalkTargetValue,
    },
    handleSubmit,
    isReadOnly: isEditReadOnly,
    quietPeriodSelect: {
      disabled: isEditReadOnly,
      items: AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions,
      onChange: setQuietPeriodSeconds,
      value: quietPeriodValue,
    },
    slackChannelSelect: {
      disabled:
        isEditReadOnly ||
        selectedSlackCredentialId === undefined ||
        slackTargetsQuery.isLoading ||
        slackTargetsQuery.isError ||
        slackChannelItems.length === 0,
      items: slackChannelItems,
      onChange: setSlackChannelId,
      placeholder: slackChannelPlaceholder,
      value: slackChannelValue,
    },
    slackCredentialSelect: {
      disabled:
        isEditReadOnly || slackCredentialsQuery.isLoading || slackCredentialsQuery.isError || slackCredentialItems.length === 0,
      items: slackCredentialItems,
      onChange: handleSlackCredentialChange,
      placeholder: slackCredentialPlaceholder,
      value: slackCredentialValue,
    },
  };
}
