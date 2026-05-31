import type { SlackOriginalContentResponse } from '@/features/hybrid-search/types/slackOriginalApi';

export const slackOriginalThreadResponse: SlackOriginalContentResponse = {
  connector: 'slack',
  entity_type: 'message',
  document_id: 'slack:message:T00000000:C00000001:1779601372.378609',
  title: '@CatchUpQA 디자인 논의사항 알려줘',
  url: 'https://catchup.slack.com/archives/C00000001/p1779601372378609',
  next_cursor: null,
  fetched_at: '2026-05-24T16:23:00Z',
  metadata: {
    team_id: 'T00000000',
    channel_id: 'C00000001',
    channel_name: 'slack-bot-test',
    thread_ts: '1779601372.378609',
    workspace_domain: 'catchup',
    users_by_id: {
      U_PARENT: {
        id: 'U_PARENT',
        name: 'sibo',
        display_name: '작성자명 text text text text text text text text',
        profile_image_url: null,
      },
      U_REPLY: {
        id: 'U_REPLY',
        name: 'designer',
        display_name: '참여자 1',
        profile_image_url: null,
      },
    },
  },
  items: [
    {
      id: '1779601372.378609',
      type: 'slack_conversations_replies_raw',
      created_at: null,
      updated_at: null,
      raw_payload: {
        ok: true,
        response_metadata: { next_cursor: '' },
        messages: [
          {
            type: 'message',
            user: 'U_PARENT',
            text: '<@U_REPLY> 디자인 논의사항 알려줘\n긴 본문은 원문이라 줄바꿈으로 보여야 합니다.',
            ts: '1779601372.378609',
            thread_ts: '1779601372.378609',
            reply_count: 2,
            reply_users: ['U_REPLY'],
            blocks: [
              {
                type: 'section',
                text: {
                  type: 'mrkdwn',
                  text: '<@U_REPLY> 디자인 논의사항 알려줘\n긴 본문은 원문이라 줄바꿈으로 보여야 합니다.',
                },
              },
            ],
          },
          {
            type: 'message',
            subtype: 'bot_message',
            username: 'CatchUpQA',
            bot_id: 'B_CATCHUP',
            bot_profile: {
              id: 'B_CATCHUP',
              app_id: 'A_CATCHUP',
              name: 'CatchUpQA',
              icons: {},
            },
            text: '요약 답변입니다.',
            ts: '1779601400.000000',
            thread_ts: '1779601372.378609',
            edited: {
              user: 'B_CATCHUP',
              ts: '1779601460.000000',
            },
            blocks: [
              {
                type: 'rich_text',
                elements: [
                  {
                    type: 'rich_text_section',
                    elements: [
                      { type: 'text', text: 'Inline code', style: { code: true } },
                      { type: 'text', text: '와 ' },
                      { type: 'text', text: 'bold', style: { bold: true } },
                      { type: 'text', text: ', ' },
                      { type: 'text', text: 'strike', style: { strike: true } },
                      { type: 'text', text: ', ' },
                      { type: 'link', url: 'https://example.com/spec', text: 'link', style: { underline: true } },
                      { type: 'text', text: ' 예시입니다.' },
                    ],
                  },
                  {
                    type: 'rich_text_list',
                    style: 'bullet',
                    elements: [
                      { type: 'rich_text_section', elements: [{ type: 'text', text: 'mention chip 필요' }] },
                      { type: 'rich_text_section', elements: [{ type: 'user', user_id: 'U_REPLY' }] },
                    ],
                  },
                  {
                    type: 'rich_text_list',
                    style: 'ordered',
                    offset: 1,
                    elements: [
                      { type: 'rich_text_section', elements: [{ type: 'text', text: 'numbered list' }] },
                      { type: 'rich_text_section', elements: [{ type: 'text', text: 'overflow 확인' }] },
                    ],
                  },
                  {
                    type: 'rich_text_quote',
                    elements: [{ type: 'text', text: 'Quote block text' }],
                  },
                  {
                    type: 'rich_text_preformatted',
                    elements: [
                      {
                        type: 'text',
                        text: "const render = 'code block';\nconsole.log(render);",
                      },
                    ],
                  },
                ],
              },
            ],
            files: [
              {
                id: 'F_DOC',
                name: 'slack-original-panel-specification-with-long-name.pdf',
                title: 'slack-original-panel-specification-with-long-name.pdf',
                mimetype: 'application/pdf',
                size: 153600,
                permalink: 'https://catchup.slack.com/files/F_DOC',
              },
              {
                id: 'F_IMG_1',
                name: 'image-1.png',
                title: 'image-1.png',
                mimetype: 'image/png',
                size: 204800,
                thumb_360: 'https://placehold.co/360x360/png?text=1',
                permalink: 'https://catchup.slack.com/files/F_IMG_1',
              },
              {
                id: 'F_IMG_2',
                name: 'image-2.png',
                title: 'image-2.png',
                mimetype: 'image/png',
                size: 204800,
                thumb_360: 'https://placehold.co/360x360/png?text=2',
                permalink: 'https://catchup.slack.com/files/F_IMG_2',
              },
              {
                id: 'F_IMG_3',
                name: 'image-3.png',
                title: 'image-3.png',
                mimetype: 'image/png',
                size: 204800,
                thumb_360: 'https://placehold.co/360x360/png?text=3',
                permalink: 'https://catchup.slack.com/files/F_IMG_3',
              },
            ],
            attachments: [
              {
                id: 1,
                title: 'Slack 원문 패널 링크 프리뷰 제목이 길어질 때',
                title_link: 'https://example.com/slack-original-panel',
                text: '링크 설명이 길어져도 한 줄에서 안정적으로 잘립니다.',
                image_url: 'https://placehold.co/560x240/png?text=Preview',
                from_url: 'https://example.com/slack-original-panel',
              },
            ],
          },
          {
            type: 'message',
            user: 'U_REPLY',
            text: '확인했습니다. 이미지 없는 파일은 파일 row로 유지하면 됩니다.',
            ts: '1779601500.000000',
            thread_ts: '1779601372.378609',
            files: [
              {
                id: 'F_IMG_NO_THUMB',
                name: 'fallback-image-without-thumb.png',
                title: 'fallback-image-without-thumb.png',
                mimetype: 'image/png',
                size: 1024,
                permalink: 'https://catchup.slack.com/files/F_IMG_NO_THUMB',
              },
            ],
          },
        ],
      },
    },
  ],
};
