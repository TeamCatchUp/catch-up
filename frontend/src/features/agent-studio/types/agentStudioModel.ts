export type AgentStudioStatus = 'active' | 'draft' | 'inactive';
export type AgentStudioFilter = 'all' | AgentStudioStatus;

export interface AgentStudioFilterItem {
  value: AgentStudioFilter;
  label: string;
}

export interface AgentStudioCardModel {
  id: string;
  agentSpecId?: number;
  status: AgentStudioStatus;
  title: string;
  description: string;
  authorName: string;
  updatedAtLabel: string;
}

export interface AgentStudioSettingsFixture {
  title: string;
  descriptionLines: readonly string[];
  channelTalkChannelLabel: string;
  quietPeriodLabel: string;
  slackWorkspaceName: string;
  slackChannelLabel: string;
  instructionHintText: string;
  instructionMaxLength: number;
}
