'use client';

import { useCallback, useState } from 'react';

import type { AnswerOption, JobRole, PreferencesFormState } from '../types/preferencesModel';

export function usePreferencesForm() {
  const [state, setState] = useState<PreferencesFormState>({
    selected_job: null,
    custom_job_text: '',
    selected_options: [],
    custom_prompt: null,
  });

  const setJob = useCallback((job: JobRole | null) => {
    setState((prev) => ({
      ...prev,
      selected_job: prev.selected_job === job ? null : job,
      custom_job_text: job !== 'custom' ? '' : prev.custom_job_text,
    }));
  }, []);

  const setCustomJobText = useCallback((text: string) => {
    setState((prev) => ({ ...prev, custom_job_text: text }));
  }, []);

  const toggleOption = useCallback((option: AnswerOption) => {
    setState((prev) => ({
      ...prev,
      selected_options: prev.selected_options.includes(option)
        ? prev.selected_options.filter((o) => o !== option)
        : [...prev.selected_options, option],
    }));
  }, []);

  const setCustomPrompt = useCallback((prompt: string | null) => {
    setState((prev) => ({ ...prev, custom_prompt: prompt }));
  }, []);

  return { state, setJob, setCustomJobText, toggleOption, setCustomPrompt };
}
