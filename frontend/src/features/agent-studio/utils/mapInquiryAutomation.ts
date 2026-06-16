import { format, parseISO } from 'date-fns';
import { ko } from 'date-fns/locale';

import type { AgentStudioCardModel } from '../types/agentStudioModel';
import type { InquiryAutomationItem } from '../types/automationApi';

const EMPTY_VALUE_LABEL = '-';

function formatNullableText(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : EMPTY_VALUE_LABEL;
}

function formatNullableDate(value: string | null | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) return EMPTY_VALUE_LABEL;

  const parsed = parseISO(trimmed);
  if (Number.isNaN(parsed.getTime())) return trimmed;

  return format(parsed, 'yyyy.MM.dd(EEE)', { locale: ko });
}

function normalizeNullableUrl(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

export function mapInquiryAutomationToAgentCard(item: InquiryAutomationItem): AgentStudioCardModel | null {
  if (item.status !== 'draft' && item.status !== 'active' && item.status !== 'inactive') return null;

  return {
    id: `inquiry-automation-${item.agent_spec_id}`,
    agentSpecId: item.agent_spec_id,
    status: item.status,
    title: formatNullableText(item.title),
    description: formatNullableText(item.guide_instruction),
    authorName: formatNullableText(item.author_name),
    authorProfileImageUrl: normalizeNullableUrl(item.author_profile_image_url),
    updatedAtLabel: formatNullableDate(item.updated_at),
  };
}

export function mapInquiryAutomationsToAgentCards(items: readonly InquiryAutomationItem[]): AgentStudioCardModel[] {
  return items.flatMap((item) => {
    const mapped = mapInquiryAutomationToAgentCard(item);
    return mapped ? [mapped] : [];
  });
}
