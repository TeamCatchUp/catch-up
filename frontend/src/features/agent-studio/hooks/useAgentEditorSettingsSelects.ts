'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { AGENT_EDITOR_SETTINGS_MESSAGES } from '../constants/agentEditorSettingsMessages';
import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../fixtures/agentStudioFixtures';
import { automationCredentialsQueries } from '../queries/automationCredentials.queries';
import { inquiryAutomationsQueries } from '../queries/inquiryAutomations.queries';
import type { AgentStudioSelectItem } from '../types/agentStudioModel';
import { mapAutomationCredentialToSelectItem, mapAutomationTargetToSelectItem } from '../utils/mapAutomationSelectItems';
import { areInquiryAutomationSettingsSelected } from '../utils/validateInquiryAutomationSettings';

const EMPTY_SELECT_ITEMS: readonly AgentStudioSelectItem[] = [];
const DEFAULT_QUIET_PERIOD_SECONDS = AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions[0]?.value ?? '60';

interface UseAgentEditorSettingsSelectsOptions {
  isEditMode: boolean;
  resolvedAgentSpecId?: number;
}

export function useAgentEditorSettingsSelects({
  isEditMode,
  resolvedAgentSpecId,
}: UseAgentEditorSettingsSelectsOptions) {
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

  const handleSlackCredentialChange = (value: string) => {
    setSlackCredentialId(value);
    setSlackChannelId('');
  };

  return {
    automationDetail,
    channelTalkSelect: {
      disabled:
        isEditReadOnly ||
        channelTalkTargetsQuery.isLoading ||
        channelTalkTargetsQuery.isError ||
        channelTalkTargetItems.length === 0,
      items: channelTalkTargetItems,
      onChange: setChannelTalkTargetId,
      placeholder: channelTalkPlaceholder,
      value: channelTalkTargetValue,
    },
    defaultQuietPeriodSeconds: Number(DEFAULT_QUIET_PERIOD_SECONDS),
    hasAutomationDetailLoadError: isEditMode && automationDetailQuery.isError,
    hasEditChannelTalkTarget: editChannelTalkTarget !== undefined,
    hasSelectedAutomationSettings,
    isAutomationDetailLoaded: automationDetailQuery.isSuccess,
    isEditReadOnly,
    quietPeriodSelect: {
      disabled: isEditReadOnly,
      items: AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions,
      onChange: setQuietPeriodSeconds,
      value: quietPeriodValue,
    },
    quietPeriodValue,
    selectedChannelTalkTarget,
    selectedSlackCredential,
    selectedSlackCredentialId,
    selectedSlackTarget,
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
        isEditReadOnly ||
        slackCredentialsQuery.isLoading ||
        slackCredentialsQuery.isError ||
        slackCredentialItems.length === 0,
      items: slackCredentialItems,
      onChange: handleSlackCredentialChange,
      placeholder: slackCredentialPlaceholder,
      value: slackCredentialValue,
    },
  };
}
