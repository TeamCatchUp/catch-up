export type JobRole = 'pm' | 'developer' | 'designer' | 'cs_ops' | 'business_strategy' | 'sales' | 'custom';

export type AnswerOption =
  | 'glossary'
  | 'background'
  | 'assignee'
  | 'similar_cases'
  | 'impact_scope'
  | 'ux_impact';

export type ThemeMode = 'system' | 'light' | 'dark';

export interface PreferencesFormState {
  selected_job: JobRole | null;
  custom_job_text: string;
  selected_options: AnswerOption[];
  custom_prompt: string | null;
}
