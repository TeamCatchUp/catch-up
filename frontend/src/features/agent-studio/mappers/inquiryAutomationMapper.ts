import { AGENT_STUDIO_LIST_FIXTURE } from '../fixtures/agentStudioFixtures';
import type { AgentStudioCardModel } from '../types/agentStudioModel';
import type { InquiryAutomationItem } from '../types/automationApi';

const FIXED_INQUIRY_CARD = AGENT_STUDIO_LIST_FIXTURE[0];

export function mapInquiryAutomationToAgentCard(item: InquiryAutomationItem): AgentStudioCardModel | null {
  if (item.status !== 'draft' && item.status !== 'active' && item.status !== 'inactive') return null;

  return {
    id: `inquiry-automation-${item.agent_spec_id}`,
    agentSpecId: item.agent_spec_id,
    status: item.status,
    title: FIXED_INQUIRY_CARD.title,
    description: FIXED_INQUIRY_CARD.description,
    authorName: FIXED_INQUIRY_CARD.authorName,
    updatedAtLabel: FIXED_INQUIRY_CARD.updatedAtLabel,
  };
}

export function mapInquiryAutomationsToAgentCards(items: readonly InquiryAutomationItem[]): AgentStudioCardModel[] {
  return items.flatMap((item) => {
    const mapped = mapInquiryAutomationToAgentCard(item);
    return mapped ? [mapped] : [];
  });
}
