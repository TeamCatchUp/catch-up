import type { CompanySize,JobLevel } from './onboardingModel';

/** POST /api/v1/onboarding 요청 바디 */
export interface UserSignUpRequest {
  name: string;
  job_level: JobLevel;
  department: string;
}

/** POST /api/v1/onboarding/admin 요청 바디 */
export interface AdminSignUpRequest {
  name: string;
  job_level: JobLevel;
  company_name: string;
  company_size: CompanySize;
  workspace_name: string;
}

/** 온보딩 가입 응답 */
export interface SignUpResponse {
  id: number;
  email: string;
  name: string;
  department: string;
  job_level: string;
  provider: string;
}
