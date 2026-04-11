/** GET /api/v1/settings/prompts 응답 */
export interface PromptSettingsResponse {
  job_role: string | null;
  custom_job_text: string | null;
  job_description: string | null;
  selected_options: string[];
  custom_prompt: string | null;
}

/** PATCH /api/v1/settings/prompts 요청 body (partial update) */
export interface PromptSettingsRequest {
  job_role?: string | null;
  custom_job_text?: string | null;
  job_description?: string | null;
  selected_options?: string[];
  custom_prompt?: string | null;
}
