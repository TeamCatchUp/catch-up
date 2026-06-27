'use client';

import { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { AGENT_STUDIO_SETTINGS_FIXTURE } from '../fixtures/agentStudioFixtures';
import { automationCredentialsQueries } from '../queries/automationCredentials.queries';
import { inquiryAutomationsMutations } from '../queries/inquiryAutomations.mutations';
import { inquiryAutomationsQueries } from '../queries/inquiryAutomations.queries';
import type { AgentStudioSelectItem } from '../types/agentStudioModel';
import type {
  AutomationCredentialItem,
  AutomationTargetItem,
  InquiryAutomationPatchRequest,
  InquiryAutomationPublishRequest,
} from '../types/automationApi';

const EMPTY_SELECT_ITEMS: readonly AgentStudioSelectItem[] = [];
const EMPTY_ITEM_PLACEHOLDER = '선택할 수 있는 항목이 없습니다';
const DEFAULT_QUIET_PERIOD_SECONDS = AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions[0]?.value ?? '60';

interface UseAgentEditorSettingsFormOptions {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

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

function normalizeGuideInstruction(value: string | null | undefined): string | null {
  const trimmedValue = value?.trim() ?? '';

  return trimmedValue.length > 0 ? trimmedValue : null;
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
  const [instructionOverride, setInstructionOverride] = useState<string | null>(null);

  const slackCredentialsQuery = useQuery(automationCredentialsQueries.credentials('slack'));
  const channelTalkTargetsQuery = useQuery(automationCredentialsQueries.targets('channel_talk'));
  const automationDetailQuery = useQuery({
    ...inquiryAutomationsQueries.detail(resolvedAgentSpecId ?? 0),
    enabled: isEditMode && resolvedAgentSpecId !== undefined,
  });
  const automationDetail = automationDetailQuery.data;

  const channelTalkTargetItems = useMemo(
    () => channelTalkTargetsQuery.data?.targets.map(mapTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [channelTalkTargetsQuery.data?.targets],
  );
  const slackCredentialItems = useMemo(
    () => slackCredentialsQuery.data?.credentials.map(mapCredentialToSelectItem) ?? EMPTY_SELECT_ITEMS,
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
  const autoSlackCredentialId = slackCredentialItems.length === 1 ? (slackCredentialItems[0]?.value ?? '') : '';
  const editSlackCredentialId =
    isEditMode && automationDetail !== undefined ? String(automationDetail.slack_credential_id) : '';
  const slackCredentialValue = slackCredentialId || editSlackCredentialId || autoSlackCredentialId;
  const selectedSlackCredentialId = slackCredentialValue === '' ? undefined : Number(slackCredentialValue);
  const slackTargetsQuery = useQuery(automationCredentialsQueries.targets('slack', selectedSlackCredentialId));
  const slackChannelValue =
    slackChannelId || (isEditMode && automationDetail !== undefined ? automationDetail.slack_channel_id : '');
  const instruction =
    instructionOverride ?? (isEditMode && automationDetail !== undefined ? (automationDetail.guide_instruction ?? '') : '');
  const isEditReadOnly = isEditMode && automationDetail?.is_editable === false;

  const publishMutation = useMutation({
    ...inquiryAutomationsMutations.publish(),
    onSuccess: () => {
      router.push('/agent-studio');
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
    onSettled: () => {
      isSubmitInFlightRef.current = false;
    },
  });

  const slackChannelItems = useMemo(
    () => slackTargetsQuery.data?.targets.map(mapTargetToSelectItem) ?? EMPTY_SELECT_ITEMS,
    [slackTargetsQuery.data?.targets],
  );
  const selectedChannelTalkTarget = useMemo(
    () => channelTalkTargetsQuery.data?.targets.find((target) => target.target_id === channelTalkTargetValue),
    [channelTalkTargetValue, channelTalkTargetsQuery.data?.targets],
  );
  const selectedSlackTarget = useMemo(
    () => slackTargetsQuery.data?.targets.find((target) => target.target_id === slackChannelValue),
    [slackChannelValue, slackTargetsQuery.data?.targets],
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
  const canSubmit = isEditMode
    ? !patchSettingsMutation.isPending &&
      automationDetailQuery.isSuccess &&
      automationDetail?.is_editable === true &&
      editChannelTalkTarget !== undefined &&
      selectedChannelTalkTarget?.credential_id !== null &&
      selectedChannelTalkTarget?.credential_id !== undefined &&
      selectedSlackCredentialId !== undefined &&
      selectedSlackTarget !== undefined
    : trimmedInstruction.length > 0 && !publishMutation.isPending;

  const handleSlackCredentialChange = (value: string) => {
    setSlackCredentialId(value);
    setSlackChannelId('');
  };

  const buildSettingsPayload = (): InquiryAutomationPublishRequest | null => {
    if (
      selectedChannelTalkTarget?.credential_id === null ||
      selectedChannelTalkTarget?.credential_id === undefined ||
      selectedSlackCredentialId === undefined ||
      selectedSlackTarget === undefined
    ) {
      return null;
    }

    return {
      channel_talk_credential_id: selectedChannelTalkTarget.credential_id,
      quiet_period_seconds: Number(quietPeriodValue),
      slack_channel: {
        credential_id: selectedSlackCredentialId,
        channel_id: selectedSlackTarget.target_id,
        channel_name: selectedSlackTarget.display_name,
      },
      guide_instruction: normalizeGuideInstruction(instruction),
    };
  };

  const buildPatchSettingsPayload = (
    settingsPayload: InquiryAutomationPublishRequest,
  ): InquiryAutomationPatchRequest | null => {
    if (automationDetail === undefined) return null;

    const patchPayload: InquiryAutomationPatchRequest = {};

    if (settingsPayload.channel_talk_credential_id !== automationDetail.channel_talk_credential_id) {
      patchPayload.channel_talk_credential_id = settingsPayload.channel_talk_credential_id;
    }

    if (
      settingsPayload.quiet_period_seconds !==
      (automationDetail.quiet_period_seconds ?? Number(DEFAULT_QUIET_PERIOD_SECONDS))
    ) {
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

    const payload = buildSettingsPayload();
    if (payload === null) return;

    isSubmitInFlightRef.current = true;

    if (isEditMode) {
      if (resolvedAgentSpecId === undefined) {
        isSubmitInFlightRef.current = false;
        return;
      }
      const patchPayload = buildPatchSettingsPayload(payload);
      if (patchPayload === null) {
        isSubmitInFlightRef.current = false;
        return;
      }

      patchSettingsMutation.mutate({ agentSpecId: resolvedAgentSpecId, body: patchPayload });
      return;
    }

    if (trimmedInstruction.length === 0) {
      isSubmitInFlightRef.current = false;
      return;
    }

    publishMutation.mutate(payload);
  };

  const activeMutation = isEditMode ? patchSettingsMutation : publishMutation;

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
    instruction,
    isReadOnly: isEditReadOnly,
    loadErrorMessage:
      isEditMode && automationDetailQuery.isError
        ? '문의 자동화 설정을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.'
        : null,
    quietPeriodSelect: {
      disabled: isEditReadOnly,
      items: AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodOptions,
      onChange: setQuietPeriodSeconds,
      value: quietPeriodValue,
    },
    setInstruction: setInstructionOverride,
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
    submitErrorMessage: activeMutation.isError
      ? isEditMode
        ? '수정에 실패했습니다. 입력값을 확인해주세요.'
        : '배포에 실패했습니다. 입력값을 확인해주세요.'
      : null,
  };
}
