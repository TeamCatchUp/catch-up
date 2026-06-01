import { describe, expect, it } from 'vitest';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';

import { parseSlackOriginalThread } from './parseSlackOriginal';

describe('parseSlackOriginalThread', () => {
  it('maps API-shaped Slack response into a thread view model', () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);

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
      editedLabel: '편집됨',
    });
    expect(thread.messages[1].blocks.some((block) => block.type === 'code_block')).toBe(true);
  });

  it('uses top-level bot icons when bot_profile is missing', () => {
    const response = {
      ...slackOriginalThreadResponse,
      items: [
        {
          ...slackOriginalThreadResponse.items[0],
          raw_payload: {
            ...slackOriginalThreadResponse.items[0].raw_payload,
            messages: [
              {
                type: 'message',
                subtype: 'bot_message',
                username: '팀원B / Catch Up',
                bot_id: 'B0TEST',
                icons: {
                  image_48: 'https://example.com/slack-app-icon.png',
                },
                text: ':scales: [결정] [문서탐색] 인텔리전스 필터',
                ts: '1779424844.293589',
              },
            ],
          },
        },
      ],
    } satisfies SlackOriginalContentResponse;

    const thread = parseSlackOriginalThread(response);

    expect(thread.messages[0]?.author).toMatchObject({
      name: '팀원B / Catch Up',
      avatarUrl: 'https://example.com/slack-app-icon.png',
      kind: 'bot',
    });
  });
});
