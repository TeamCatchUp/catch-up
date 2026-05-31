import { describe, expect, it } from 'vitest';

import { slackOriginalPreviewResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';

import { parseSlackOriginalThread } from './parseSlackOriginal';

describe('parseSlackOriginalThread', () => {
  it('maps API-shaped Slack response into a thread view model', () => {
    const thread = parseSlackOriginalThread(slackOriginalPreviewResponse);

    expect(thread).toMatchObject({
      documentId: 'slack:message:T00000000:C00000001:1779601372.378609',
      title: '@CatchUpQA 디자인 논의사항 알려줘',
      channelName: 'slack-bot-test',
      commentCount: 2,
    });
    expect(thread.participantNames).toContain('작성자명 text text text text text text text text');
    expect(thread.participantNames).toContain('CatchUpQA');
    expect(thread.messages).toHaveLength(3);
    expect(thread.messages[1]).toMatchObject({
      author: { name: 'CatchUpQA', kind: 'bot' },
      editedLabel: '1시간 전 편집됨',
    });
    expect(thread.messages[1].blocks.some((block) => block.type === 'code_block')).toBe(true);
  });
});
