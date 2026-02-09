'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { connectorQueries } from '../../api/onboarding.queries';
import type { ConnectorFormData } from '../../model/onboarding.types';
import { ConnectorSelect } from '../ConnectorSelect';
import { StepIndicator } from '../StepIndicator';
import { StepNavButtons } from '../StepNavButtons';

interface ConnectorStepProps {
  defaultValues: {
    jiraAccountId: string;
    githubAccountId: string;
    slackAccountId: string;
  };
  onSubmit: (data: ConnectorFormData) => void;
  onBack: () => void;
}

export function ConnectorStep({ defaultValues, onSubmit, onBack }: ConnectorStepProps) {
  const { data: connectors } = useQuery(connectorQueries.list());

  const [jiraAccountId, setJiraAccountId] = useState(defaultValues.jiraAccountId);
  const [githubAccountId, setGithubAccountId] = useState(defaultValues.githubAccountId);
  const [slackAccountId, setSlackAccountId] = useState(defaultValues.slackAccountId);

  const handleNext = () => {
    onSubmit({
      jiraAccountId: jiraAccountId || undefined,
      githubAccountId: githubAccountId || undefined,
      slackAccountId: slackAccountId || undefined,
    });
  };

  return (
    <div className="flex size-full flex-col justify-between">
      <div className="flex flex-col gap-12">
        {/* 헤더 영역: 스텝 인디케이터 + 타이틀 + 설명 */}
        <div className="flex flex-col gap-4">
          <StepIndicator totalSteps={2} currentStep={2} />
          <h1 className="text-display-large tracking-tight text-gray-80">
            협업 툴 연동을 위해
            <br />
            사용중인 계정을 선택해주세요
          </h1>
          <p className="text-body-large tracking-tight text-gray-50">
            선택해주신 계정을 기준으로 정보를 정리해드려요.
          </p>
        </div>

        {/* 폼 영역 */}
        <div className="flex flex-col gap-6">
          <ConnectorSelect
            label="Jira"
            placeholder="사용중인 Jira 계정을 선택하세요."
            accounts={connectors?.jira ?? []}
            value={jiraAccountId}
            onChange={setJiraAccountId}
          />
          <ConnectorSelect
            label="Github"
            placeholder="사용중인 Github 계정을 선택하세요."
            accounts={connectors?.github ?? []}
            value={githubAccountId}
            onChange={setGithubAccountId}
          />
          <ConnectorSelect
            label="Slack"
            placeholder="사용중인 Slack 계정을 선택하세요."
            accounts={connectors?.slack ?? []}
            value={slackAccountId}
            onChange={setSlackAccountId}
          />
        </div>
      </div>

      <StepNavButtons
        onBack={onBack}
        onNext={handleNext}
      />
    </div>
  );
}
