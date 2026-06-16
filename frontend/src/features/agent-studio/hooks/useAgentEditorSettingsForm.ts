'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../fixtures/agentStudioFixtures';
import { automationCredentialsQueries } from '../queries/automationCredentials.queries';
import { inquiryAutomationsMutations } from '../queries/inquiryAutomations.mutations';
import type { AgentStudioSelectItem } from '../types/agentStudioModel';
import type { AutomationCredentialItem, AutomationTargetItem } from '../types/automationApi';

const EMPTY_SELECT_ITEMS: readonly AgentStudioSelectItem[] = [];
const EMPTY_ITEM_PLACEHOLDER = '선택할 수 있는 항목이 없습니다';

function mapCredentialToSelectItem(credential: AutomationCredentialItem): AgentStudioSelectItem {
  return {
    value: String(credential.credential_id),
    label: credential.display_name,
    disabled: !credential.is_configured,
  };
}

function mapTargetToSelectItem(target: AutomationTargetItem): AgentStudioSelectItem {
  return {
    value: target.target_id,
    label: target.display_name,
    disabled: !target.is_accessible,
  };
}

export function useAgentEditorSettingsForm() {
  const router = useRouter();
  const [channelTalkTargetId, setChannelTalkTargetId] = useState('');
  const [quietPeriodSeconds, setQuietPeriodSeconds] = useState(
    AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions[0]?.value ?? '60',
  );
  const [slackCredentialId, setSlackCredentialId] = useState('');
  const [slackChannelId, setSlackChannelId] = useState('');
  const [instruction, setInstruction] = useState('');

  const slackCredentialsQuery = useQuery(automationCredentialsQueries.credentials('slack'));
  const channelTalkTargetsQuery = useQuery(automationCredentialsQueries.targets('channel_talk'));

  const channelTalkTargetItems = useMemo(
    () => channelTalkTargetsQuery.data?.targets.map(mapTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [channelTalkTargetsQuery.data?.targets],
  );
  const slackCredentialItems = useMemo(
    () => slackCredentialsQuery.data?.credentials.map(mapCredentialToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [slackCredentialsQuery.data?.credentials],
  );
  const autoSlackCredentialId = slackCredentialItems.length === 1 ? (slackCredentialItems[0]?.value ?? '') : '';
  const slackCredentialValue = slackCredentialId || autoSlackCredentialId;
  const selectedSlackCredentialId = slackCredentialValue === '' ? undefined : Number(slackCredentialValue);
  const slackTargetsQuery = useQuery(automationCredentialsQueries.targets('slack', selectedSlackCredentialId));
  const publishMutation = useMutation({
    ...inquiryAutomationsMutations.publish(),
    onSuccess: () => {
      router.push('/agent-studio');
    },
  });

  const slackChannelItems = useMemo(
    () => slackTargetsQuery.data?.targets.map(mapTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [slackTargetsQuery.data?.targets],
  );
  const selectedChannelTalkTarget = useMemo(
    () => channelTalkTargetsQuery.data?.targets.find((target) => target.target_id === channelTalkTargetId),
    [channelTalkTargetId, channelTalkTargetsQuery.data?.targets],
  );
  const selectedSlackTarget = useMemo(
    () => slackTargetsQuery.data?.targets.find((target) => target.target_id === slackChannelId),
    [slackChannelId, slackTargetsQuery.data?.targets],
  );
  const trimmedInstruction = instruction.trim();

  const channelTalkPlaceholder = channelTalkTargetsQuery.isError
    ? '채널톡 채널을 불러오지 못했습니다'
    : channelTalkTargetsQuery.isSuccess && channelTalkTargetItems.length === 0
      ? EMPTY_ITEM_PLACEHOLDER
      : AGENT_STUDIO_SETTINGS_FIXTURE.channelTalkChannelLabel;
  const slackCredentialPlaceholder = slackCredentialsQuery.isError
    ? 'Slack 권한을 불러오지 못했습니다'
    : slackCredentialsQuery.isSuccess && slackCredentialItems.length === 0
      ? EMPTY_ITEM_PLACEHOLDER
      : AGENT_STUDIO_SETTINGS_FIXTURE.slackWorkspaceName;
  const slackChannelPlaceholder = slackTargetsQuery.isError
    ? 'Slack 채널을 불러오지 못했습니다'
    : selectedSlackCredentialId !== undefined && slackTargetsQuery.isSuccess && slackChannelItems.length === 0
      ? EMPTY_ITEM_PLACEHOLDER
      : AGENT_STUDIO_SETTINGS_FIXTURE.slackChannelLabel;
  const canPublish = trimmedInstruction.length > 0 && !publishMutation.isPending;

  const handleSlackCredentialChange = (value: string) => {
    setSlackCredentialId(value);
    setSlackChannelId('');
  };

  const handlePublish = () => {
    if (
      selectedChannelTalkTarget?.credential_id === null ||
      selectedChannelTalkTarget?.credential_id === undefined ||
      selectedSlackCredentialId === undefined ||
      selectedSlackTarget === undefined ||
      trimmedInstruction.length === 0
    ) {
      return;
    }

    publishMutation.mutate({
      channel_talk_credential_id: selectedChannelTalkTarget.credential_id,
      quiet_period_seconds: Number(quietPeriodSeconds),
      slack_channel: {
        credential_id: selectedSlackCredentialId,
        channel_id: selectedSlackTarget.target_id,
        channel_name: selectedSlackTarget.display_name,
      },
      guide_instruction: trimmedInstruction,
    });
  };

  return {
    canPublish,
    channelTalkSelect: {
      disabled:
        channelTalkTargetsQuery.isLoading || channelTalkTargetsQuery.isError || channelTalkTargetItems.length === 0,
      items: channelTalkTargetItems,
      onChange: setChannelTalkTargetId,
      placeholder: channelTalkPlaceholder,
      value: channelTalkTargetId,
    },
    handlePublish,
    instruction,
    isPublishError: publishMutation.isError,
    quietPeriodSelect: {
      items: AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions,
      onChange: setQuietPeriodSeconds,
      value: quietPeriodSeconds,
    },
    setInstruction,
    slackChannelSelect: {
      disabled:
        selectedSlackCredentialId === undefined ||
        slackTargetsQuery.isLoading ||
        slackTargetsQuery.isError ||
        slackChannelItems.length === 0,
      items: slackChannelItems,
      onChange: setSlackChannelId,
      placeholder: slackChannelPlaceholder,
      value: slackChannelId,
    },
    slackCredentialSelect: {
      disabled: slackCredentialsQuery.isLoading || slackCredentialsQuery.isError || slackCredentialItems.length === 0,
      items: slackCredentialItems,
      onChange: handleSlackCredentialChange,
      placeholder: slackCredentialPlaceholder,
      value: slackCredentialValue,
    },
  };
}
