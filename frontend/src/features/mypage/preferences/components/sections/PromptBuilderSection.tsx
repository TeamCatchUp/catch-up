'use client';

import { usePreferencesForm } from '../../hooks/usePreferencesForm';
import SectionBar from '../SectionBar';
import AnswerOptionsStep from '../steps/AnswerOptionsStep';
import CustomPromptStep from '../steps/CustomPromptStep';
import JobSelectionStep from '../steps/JobSelectionStep';

// TODO: 현재 로컬 state만 사용. 백엔드 API 준비되면 prompt.queries/mutations 연동 필요
export default function PromptBuilderSection() {
  const { state, setJob, setCustomJobText, setJobDescription, toggleOption, setCustomPrompt } = usePreferencesForm();

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
        <AnswerOptionsStep
          selectedOptions={state.selected_options}
          onToggleOption={toggleOption}
        />
        <CustomPromptStep
          customPrompt={state.custom_prompt}
          onSave={setCustomPrompt}
        />
      </div>
    </div>
  );
}
