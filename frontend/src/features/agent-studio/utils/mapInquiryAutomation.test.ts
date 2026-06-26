import { describe, expect, it } from 'vitest';

import type { InquiryAutomationItem } from '../types/automationApi';
import { mapInquiryAutomationsToAgentCards, mapInquiryAutomationToAgentCard } from './mapInquiryAutomation';

const baseAutomation: InquiryAutomationItem = {
  agent_spec_id: 42,
  status: 'active',
  channel_talk_credential_id: 10,
  slack_channel_id: 'C123',
  slack_credential_id: 20,
  guide_instruction: '짧게 답변',
  quiet_period_seconds: 60,
  trigger_id: 100,
  is_editable: true,
};

describe('mapInquiryAutomation', () => {
  it('maps missing display fields to dash labels', () => {
    expect(mapInquiryAutomationToAgentCard(baseAutomation)).toEqual({
      id: 'inquiry-automation-42',
      agentSpecId: 42,
      status: 'active',
      title: '-',
      description: '짧게 답변',
      authorName: '-',
      authorProfileImageUrl: null,
      updatedAtLabel: '-',
      isEditable: true,
    });
  });

  it('maps backend display fields when they are present', () => {
    expect(
      mapInquiryAutomationToAgentCard({
        ...baseAutomation,
        title: '실제 문의 대응 Agent',
        author_name: '홍길동',
        updated_at: '2026-06-16T02:00:00.000Z',
        author_profile_image_url: 'https://example.com/profile.png',
      }),
    ).toMatchObject({
      title: '실제 문의 대응 Agent',
      description: '짧게 답변',
      authorName: '홍길동',
      authorProfileImageUrl: 'https://example.com/profile.png',
      updatedAtLabel: '2026.06.16(화)',
    });
  });

  it('maps missing guide instruction to a dash description', () => {
    expect(mapInquiryAutomationToAgentCard({ ...baseAutomation, guide_instruction: null })?.description).toBe('-');
  });

  it('maps inactive status without changing the fixed copy', () => {
    expect(mapInquiryAutomationToAgentCard({ ...baseAutomation, status: 'inactive' })?.status).toBe('inactive');
  });

  it('maps draft status when the backend returns a draft automation row', () => {
    expect(mapInquiryAutomationToAgentCard({ ...baseAutomation, status: 'draft' })?.status).toBe('draft');
  });

  it('filters out rows with an unexpected runtime status', () => {
    const invalid = { ...baseAutomation, agent_spec_id: 43, status: 'paused' } as unknown as InquiryAutomationItem;

    expect(mapInquiryAutomationsToAgentCards([baseAutomation, invalid])).toHaveLength(1);
  });
});
