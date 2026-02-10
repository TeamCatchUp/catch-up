/** useFunnel 스텝별 context 타입 */
export type OnboardingSteps = {
  Profile: {
    name?: string;
    position?: string;
    rank?: string;
    department?: string;
  };

  OrgInfo: {
    name: string;
    position: string;
    rank: string;
    company_name?: string;
    team_size?: string;
  };

  Connector: {
    name: string;
    position: string;
    rank: string;
    department?: string;
    company_name?: string;
    team_size?: string;
    jira_account_id?: string;
    github_account_id?: string;
    slack_account_id?: string;
  };

  Complete: {
    name: string;
    position: string;
    rank: string;
    department?: string;
    company_name?: string;
    team_size?: string;
    jira_account_id?: string;
    github_account_id?: string;
    slack_account_id?: string;
  };
};

export interface ProfileFormData {
  name: string;
  position: string;
  rank: string;
  department?: string;
}

export interface OrgInfoFormData {
  company_name: string;
  team_size: string;
}

export interface ConnectorFormData {
  jira_account_id?: string;
  github_account_id?: string;
  slack_account_id?: string;
}

export interface ConnectorAccount {
  id: string;
  name: string;
  email: string;
  picture: string | null;
}

export interface ConnectorOptions {
  jira: ConnectorAccount[];
  github: ConnectorAccount[];
  slack: ConnectorAccount[];
}

/** POST /api/v1/onboarding/complete 요청 바디 */
export interface OnboardingCompleteRequest {
  name: string;
  position: string;
  rank: string;
  department?: string;
  company_name?: string;
  team_size?: string;
  connectors: ConnectorFormData;
}
