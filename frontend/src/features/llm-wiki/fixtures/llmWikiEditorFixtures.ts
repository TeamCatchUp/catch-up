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
 */
export const EDITOR_SKELETON_DOC: JSONContent = {
  type: 'doc',
  content: [
    {
      type: 'heading',
      attrs: { level: 2, origin: null, claimIds: null },
      content: [{ type: 'text', text: '현황' }],
    },
    {
      type: 'paragraph',
      attrs: { origin: 'system', claimIds: ['c_1', 'c_2'] },
      content: [{ type: 'text', text: '8월 들어 결제 실패가 증가했다.' }],
    },
    {
      type: 'bulletList',
      attrs: { origin: null, claimIds: null },
      content: [
        {
          type: 'listItem',
          attrs: { origin: null, claimIds: null },
          content: [
            {
              type: 'paragraph',
              attrs: { origin: null, claimIds: null },
              content: [{ type: 'text', text: 'PG사 응답 지연' }],
            },
          ],
        },
        {
          type: 'listItem',
          attrs: { origin: null, claimIds: null },
          content: [
            {
              type: 'paragraph',
              attrs: { origin: null, claimIds: null },
              content: [{ type: 'text', text: '재시도 정책 미적용' }],
            },
          ],
        },
      ],
    },
    {
      type: 'paragraph',
      attrs: { origin: 'human', claimIds: null },
      content: [{ type: 'text', text: '검토자 메모: 원인 확인 중.' }],
    },
  ],
};
