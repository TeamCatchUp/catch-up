/** GET /api/v1/settings/prompts 응답 */
export interface CustomPromptResponse {
  custom_prompt: string | null;
}

/** PATCH /api/v1/settings/prompts 요청 body */
export interface CustomPromptRequest {
  custom_prompt: string | null;
}
