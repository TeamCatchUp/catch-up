'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { promptMutations } from '../../queries/prompt.mutations';
import { promptQueries } from '../../queries/prompt.queries';
import type { PromptSettingsResponse } from '../../types/preferencesApi';
import type { AnswerOption, JobRole } from '../../types/preferencesModel';
import {
  emptyToNull,
  jobRoleFromApi,
  jobRoleToApi,
  nullToEmpty,
  optionsFromApi,
  optionsToApi,
} from '../../utils/promptMapper';
import SectionBar from '../SectionBar';
import AnswerOptionsStep from '../steps/AnswerOptionsStep';
import CustomPromptStep from '../steps/CustomPromptStep';
import JobSelectionStep from '../steps/JobSelectionStep';

export default function PromptBuilderSection() {
  const queryClient = useQueryClient();
  const queryKey = promptQueries.settings().queryKey;
  const { data, isLoading } = useQuery(promptQueries.settings());

  const updateMutation = useMutation({
    ...promptMutations.updateSettings(),
    onMutate: async (body) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<PromptSettingsResponse>(queryKey);

      if (previous) {
        queryClient.setQueryData<PromptSettingsResponse>(queryKey, {
          ...previous,
          ...Object.fromEntries(Object.entries(body).filter(([, v]) => v !== undefined)),
        });
      }

      return { previous };
    },
    onError: (_err, _body, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  /* ── Query 데이터 → UI 값 변환 ── */
  const selectedJob = jobRoleFromApi(data?.job_role ?? null);
  const customJobText = nullToEmpty(data?.custom_job_text ?? null);
  const jobDescription = nullToEmpty(data?.job_description ?? null);
  const selectedOptions = optionsFromApi(data?.selected_options ?? []);
  const customPrompt = data?.custom_prompt ?? null;

  /* ── Step 1: 직무 선택 — 저장 버튼으로 통일 ── */
  const handleSaveJob = (job: JobRole | null, newCustomJobText: string, newJobDescription: string) => {
    if (job === null) {
      updateMutation.mutate({ job_role: null, custom_job_text: null, job_description: null });
    } else {
      updateMutation.mutate({
        job_role: jobRoleToApi(job),
        custom_job_text: job === 'custom' ? emptyToNull(newCustomJobText) : null,
        job_description: emptyToNull(newJobDescription),
      });
    }
  };

  /* ── Step 2: 답변 옵션 콜백 ── */
  const handleToggleOption = (option: AnswerOption) => {
    const updated = selectedOptions.includes(option)
      ? selectedOptions.filter((o) => o !== option)
      : [...selectedOptions, option];
    updateMutation.mutate({ selected_options: optionsToApi(updated) });
  };

  /* ── Step 3: 커스텀 프롬프트 콜백 ── */
  const handleSavePrompt = (value: string) => {
    updateMutation.mutate({ custom_prompt: emptyToNull(value) });
  };

  return (
    <div className="flex flex-col">
      <SectionBar title="프롬프트 빌더" />
      <div className="px-4">
        <JobSelectionStep
          selectedJob={selectedJob}
          customJobText={customJobText}
          jobDescription={jobDescription}
          onSaveJob={handleSaveJob}
        />
        <AnswerOptionsStep selectedOptions={selectedOptions} onToggleOption={handleToggleOption} />
        <CustomPromptStep customPrompt={customPrompt} onSave={handleSavePrompt} isLoading={isLoading} />
      </div>
    </div>
  );
}
