'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { usePreferencesForm } from '../../hooks/usePreferencesForm';
import { promptMutations } from '../../queries/prompt.mutations';
import { promptQueries } from '../../queries/prompt.queries';
import SectionBar from '../SectionBar';
import AnswerOptionsStep from '../steps/AnswerOptionsStep';
import CustomPromptStep from '../steps/CustomPromptStep';
import JobSelectionStep from '../steps/JobSelectionStep';

// TODO: 직무 선택/답변 옵션은 로컬 state만 사용. 백엔드 API 준비되면 연동 필요
export default function PromptBuilderSection() {
  const queryClient = useQueryClient();
  const { state, setJob, setCustomJobText, setJobDescription, toggleOption } = usePreferencesForm();

  // 커스텀 프롬프트 — 기존 API 연동 유지
  const { data, isLoading } = useQuery(promptQueries.customPrompt());
  const customPrompt = data?.custom_prompt ?? null;

  const updateMutation = useMutation({
    ...promptMutations.updateCustomPrompt(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: promptQueries.all() });
    },
  });

  const handleSavePrompt = (value: string) => {
    updateMutation.mutate({ custom_prompt: value });
  };

  return (
    <div className="flex flex-col">
      <SectionBar title="프롬프트 빌더" />
      <div className="px-4">
        <JobSelectionStep
          selectedJob={state.selected_job}
          customJobText={state.custom_job_text}
          jobDescription={state.job_description}
          onJobChange={setJob}
          onCustomJobTextChange={setCustomJobText}
          onJobDescriptionChange={setJobDescription}
        />
        <AnswerOptionsStep selectedOptions={state.selected_options} onToggleOption={toggleOption} />
        <CustomPromptStep
          customPrompt={customPrompt}
          onSave={handleSavePrompt}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
