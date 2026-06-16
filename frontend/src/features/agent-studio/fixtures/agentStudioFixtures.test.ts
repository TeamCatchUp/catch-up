import { describe, expect, it } from 'vitest';

import {
  AGENT_STUDIO_FILTERS,
  AGENT_STUDIO_LIST_FIXTURE,
  AGENT_STUDIO_SETTINGS_FIXTURE,
  getAgentCardsByStatus,
} from './agentStudioFixtures';

describe('agentStudioFixtures', () => {
  it('provides the exact filter labels used by the list page', () => {
    expect(AGENT_STUDIO_FILTERS.map((item) => item.label)).toEqual(['전체', '운영중', '제작중', '사용 안함']);
  });

  it('groups the default cards by status', () => {
    expect(getAgentCardsByStatus('all')).toHaveLength(2);
    expect(getAgentCardsByStatus('active')).toHaveLength(1);
    expect(getAgentCardsByStatus('draft')).toHaveLength(0);
    expect(getAgentCardsByStatus('inactive')).toHaveLength(1);
  });

  it('keeps the editor defaults aligned with the setup screen', () => {
    expect(AGENT_STUDIO_SETTINGS_FIXTURE.quietPeriodLabel).toBe('1분');
    expect(AGENT_STUDIO_SETTINGS_FIXTURE.slackWorkspaceName).toBe('Catch Up');
    expect(AGENT_STUDIO_LIST_FIXTURE[0]?.title).toBe('문의 대응 리포트 만들기');
  });
});
