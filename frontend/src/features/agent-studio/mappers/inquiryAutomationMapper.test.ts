import { describe, expect, it } from 'vitest';

import type { InquiryAutomationItem } from '../types/automationApi';
import { mapInquiryAutomationToAgentCard, mapInquiryAutomationsToAgentCards } from './inquiryAutomationMapper';

const baseAutomation: InquiryAutomationItem = {
  agent_spec_id: 42,
  status: 'active',
  channel_talk_credential_id: 10,
  slack_channel_id: 'C123',
  slack_credential_id: 20,
  guide_instruction: '짧게 답변',
  quiet_period_seconds: 60,
  trigger_id: 100,
};

describe('inquiryAutomationMapper', () => {
  it('maps an active inquiry automation to the fixed Agent Studio card copy', () => {
    expect(mapInquiryAutomationToAgentCard(baseAutomation)).toEqual({
      id: 'inquiry-automation-42',
      agentSpecId: 42,
      status: 'active',
      title: '문의 대응 리포트 만들기',
      description:
        '현재 리팩토링 진행 상황과 예정된 배포 일정을 중심으로 인수인계를 진행합니다. QA 일정과 운영 반영 시 유의사항을 함께 공유합니다.',
      authorName: '이진수',
      updatedAtLabel: '2020.00.00(월)',
    });
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
