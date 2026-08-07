import type { JSONContent } from '@tiptap/react';

/**
 * 에디터 스토리용 Tiptap JSON 픽스처.
 *
 * llmWikiFixtures.ts 와 합치지 않는다. 그쪽은 백엔드 ERD를 따르는 도메인 mock([BE]/[SPEC] 주석)이고,
 * 이건 Tiptap 내부 표현이라 백엔드에 대응물이 없다. 한 파일에 섞으면 어댑터가 생길 때
 * 어느 게 계약이고 어느 게 에디터 내부 표현인지 구분이 안 된다.
 *
 * 골격 단계라 표·체크박스·콜아웃은 넣지 않는다 — 스키마에 없어 enableContentCheck가 잡는다.
 * origin·claimIds는 화면에 나오지 않지만 왕복 보존을 스토리에서도 밟기 위해 실어둔다.
 *
 * 모든 블록에 id를 미리 넣는다 — 어댑터가 blocks[]를 실어 올 실제 흐름의 대표다.
 * id가 없으면 UniqueID가 마운트 시 채워 넣는 트랜잭션을 만들어 onUpdate가 1회 발사된다
 * (WithContent 스토리의 "마운트 직후 onUpdate 0회" 불변식은 id 있는 문서에서만 성립한다).
 */
/** 2차 블록(체크박스·표·콜아웃) 렌더 검증용 — JSON 로드 경로가 스키마와 맞는지 스토리에서 밟는다 */
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
