import type { JSONContent } from '@tiptap/react';

/**
 * 에디터 스토리용 Tiptap JSON 픽스처. 백엔드 계약이 아니라 Tiptap 내부 표현이다.
 * 모든 블록에 id를 미리 넣는다 — 없으면 UniqueID가 마운트 시 트랜잭션을 만들어 onUpdate가 발사된다.
 */

/** 2차 블록(체크박스·표·콜아웃) 렌더 검증용 */
export const EDITOR_PHASE2_DOC: JSONContent = {
  type: 'doc',
  content: [
    {
      type: 'taskList',
      attrs: { id: 'blk_tasks', origin: 'human', claimIds: null },
      content: [
        {
          type: 'taskItem',
          attrs: { id: 'blk_task_1', checked: true, origin: 'human', claimIds: null },
          content: [{ type: 'paragraph', content: [{ type: 'text', text: 'PG사 응답 로그 확보' }] }],
        },
        {
          type: 'taskItem',
          attrs: { id: 'blk_task_2', checked: false, origin: 'human', claimIds: null },
          content: [{ type: 'paragraph', content: [{ type: 'text', text: '재시도 정책 문서화' }] }],
        },
      ],
    },
    {
      type: 'callout',
      attrs: { id: 'blk_callout', origin: 'system', claimIds: ['c_3'] },
      content: [{ type: 'paragraph', content: [{ type: 'text', text: '이 수치는 새벽 배치 기준이다.' }] }],
    },
    {
      type: 'table',
      attrs: { id: 'blk_table', origin: null, claimIds: null },
      content: [
        {
          type: 'tableRow',
          content: [
            { type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: '항목' }] }] },
            { type: 'tableHeader', content: [{ type: 'paragraph', content: [{ type: 'text', text: '값' }] }] },
          ],
        },
        {
          type: 'tableRow',
          content: [
            { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: '실패율' }] }] },
            { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: '3.2%' }] }] },
          ],
        },
      ],
    },
  ],
};

export const EDITOR_SKELETON_DOC: JSONContent = {
  type: 'doc',
  content: [
    {
      type: 'heading',
      attrs: { id: 'blk_h_status', level: 2, origin: null, claimIds: null },
      content: [{ type: 'text', text: '현황' }],
    },
    {
      type: 'paragraph',
      attrs: { id: 'blk_p_claim', origin: 'system', claimIds: ['c_1', 'c_2'] },
      content: [{ type: 'text', text: '8월 들어 결제 실패가 증가했다.' }],
    },
    {
      type: 'bulletList',
      attrs: { id: 'blk_ul', origin: null, claimIds: null },
      content: [
        {
          type: 'listItem',
          attrs: { id: 'blk_li_pg', origin: null, claimIds: null },
          content: [
            {
              type: 'paragraph',
              attrs: { id: 'blk_p_pg', origin: null, claimIds: null },
              content: [{ type: 'text', text: 'PG사 응답 지연' }],
            },
          ],
        },
        {
          type: 'listItem',
          attrs: { id: 'blk_li_retry', origin: null, claimIds: null },
          content: [
            {
              type: 'paragraph',
              attrs: { id: 'blk_p_retry', origin: null, claimIds: null },
              content: [{ type: 'text', text: '재시도 정책 미적용' }],
            },
          ],
        },
      ],
    },
    {
      type: 'paragraph',
      attrs: { id: 'blk_p_memo', origin: 'human', claimIds: null },
      content: [{ type: 'text', text: '검토자 메모: 원인 확인 중.' }],
    },
  ],
};
