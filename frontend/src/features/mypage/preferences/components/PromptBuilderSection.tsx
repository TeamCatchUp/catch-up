'use client';

import { usePreferencesForm } from '../hooks/usePreferencesForm';
import AnswerOptionsStep from './AnswerOptionsStep';
import CustomPromptStep from './CustomPromptStep';
import JobSelectionStep from './JobSelectionStep';
import SectionBar from './SectionBar';

export default function PromptBuilderSection() {
  const { state, setJob, setCustomJobText, toggleOption, setCustomPrompt } = usePreferencesForm();

  return (
    <div className="flex flex-col">
      <SectionBar title="프롬프트 빌더" />
      <div className="px-4">
        <JobSelectionStep
          selectedJob={state.selected_job}
          customJobText={state.custom_job_text}
          onJobChange={setJob}
          onCustomJobTextChange={setCustomJobText}
        />
        <AnswerOptionsStep
          selectedOptions={state.selected_options}
          onToggleOption={toggleOption}
        />
        <CustomPromptStep
          customPrompt={state.custom_prompt}
          onSave={setCustomPrompt}
          onDelete={() => setCustomPrompt(null)}
        />
      </div>
    </div>
  );
}
