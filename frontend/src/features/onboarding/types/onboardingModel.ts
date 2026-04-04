/** 백엔드 JobLevel enum */
export type JobLevel = 'executive' | 'leader' | 'member';

/** 백엔드 CompanySize enum */
export type CompanySize = 'small' | 'medium' | 'large' | 'enterprise';

/** useFunnel 스텝별 context 타입 */
export type OnboardingSteps = {
  Profile: {
    name?: string;
    job_level?: JobLevel;
    department?: string;
  };

  OrgInfo: {
    name: string;
    job_level: JobLevel;
    company_name?: string;
    company_size?: CompanySize;
  };

  Complete: {
    name: string;
    job_level: JobLevel;
    department?: string;
    company_name?: string;
    company_size?: CompanySize;
  };
};

export interface ProfileFormData {
  name: string;
  job_level: JobLevel;
  department?: string;
}

export interface OrgInfoFormData {
  company_name: string;
  company_size: CompanySize;
}
