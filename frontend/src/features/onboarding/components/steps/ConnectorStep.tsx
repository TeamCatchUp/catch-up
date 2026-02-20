'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { connectorQueries } from '../../queries';
import type { ConnectorFormData } from '../../types/onboarding';
import { ConnectorSelect } from '../ConnectorSelect';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface ConnectorStepProps {
  defaultValues: {
    jira_account_id: string;
    github_account_id: string;
    slack_account_id: string;
  };
  onSubmit: (data: ConnectorFormData) => void;
  onBack: (data: ConnectorFormData) => void;
}

export function ConnectorStep({ defaultValues, onSubmit, onBack }: ConnectorStepProps) {
  const { data: connectors } = useQuery(connectorQueries.list());

  const [atlassianAccountId, setAtlassianAccountId] = useState(defaultValues.jira_account_id);
  const [githubAccountId, setGithubAccountId] = useState(defaultValues.github_account_id);
  const [slackAccountId, setSlackAccountId] = useState(defaultValues.slack_account_id);

  const [atlassianDisabled, setAtlassianDisabled] = useState(false);
  const [githubDisabled, setGithubDisabled] = useState(false);
  const [slackDisabled, setSlackDisabled] = useState(false);

  const isComplete =
    (atlassianAccountId || atlassianDisabled) &&
    (githubAccountId || githubDisabled) &&
    (slackAccountId || slackDisabled);

  const handleNext = () => {
    onSubmit({
      jira_account_id: atlassianAccountId || undefined,
      github_account_id: githubAccountId || undefined,
      slack_account_id: slackAccountId || undefined,
    });
  };

  return (
    <div className="flex size-full flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          <StepIndicator totalSteps={2} currentStep={2} />
          <h1 className="text-display-large text-gray-80 tracking-tight">
            협업 툴 연동을 위해
            <br />
            사용중인 계정을 선택해주세요
          </h1>
          <p className="text-body-large tracking-tight text-gray-50">선택해주신 계정을 기준으로 정보를 정리해드려요.</p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          <ConnectorSelect
            label="Atlassian"
            placeholder="사용중인 Atlassian 계정을 선택하세요."
            accounts={connectors?.jira ?? []}
            value={atlassianAccountId}
            onChange={setAtlassianAccountId}
            disabled={atlassianDisabled}
            onDisabledChange={setAtlassianDisabled}
          />
          <ConnectorSelect
            label="Github"
            placeholder="사용중인 Github 계정을 선택하세요."
            accounts={connectors?.github ?? []}
            value={githubAccountId}
            onChange={setGithubAccountId}
            disabled={githubDisabled}
            onDisabledChange={setGithubDisabled}
          />
          <ConnectorSelect
            label="Slack"
            placeholder="사용중인 Slack 계정을 선택하세요."
            accounts={connectors?.slack ?? []}
            value={slackAccountId}
            onChange={setSlackAccountId}
            disabled={slackDisabled}
            onDisabledChange={setSlackDisabled}
          />
        </div>
      </div>

      <StepNavButtons
        onBack={() =>
          onBack({
            jira_account_id: atlassianAccountId || undefined,
            github_account_id: githubAccountId || undefined,
            slack_account_id: slackAccountId || undefined,
          })
        }
        onNext={handleNext}
        isNextDisabled={!isComplete}
      />
    </div>
  );
}
