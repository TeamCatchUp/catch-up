/** useFunnel 스텝별 context 타입 */
export type OnboardingSteps = {
  Welcome: Record<string, never>;

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
    companyName?: string;
    teamSize?: string;
  };

  Connector: {
    name: string;
    position: string;
    rank: string;
    department?: string;
    companyName?: string;
    teamSize?: string;
    jiraAccountId?: string;
    githubAccountId?: string;
    slackAccountId?: string;
  };

  Complete: {
    name: string;
    position: string;
    rank: string;
    department?: string;
    companyName?: string;
    teamSize?: string;
    jiraAccountId?: string;
    githubAccountId?: string;
    slackAccountId?: string;
  };
};

export interface ProfileFormData {
  name: string;
  position: string;
  rank: string;
  department?: string;
}

export interface OrgInfoFormData {
  companyName: string;
  teamSize: string;
}

export interface ConnectorFormData {
  jiraAccountId?: string;
  githubAccountId?: string;
  slackAccountId?: string;
}

export interface ConnectorAccount {
  id: string;
  name: string;
  email: string;
  picture: string | null;
  tag: string;
}

export interface ConnectorOptions {
  jira: ConnectorAccount[];
  github: ConnectorAccount[];
  slack: ConnectorAccount[];
}
