// dev preview 갤러리용 OriginalContent 목 데이터 — content_type별 케이스 매트릭스.
// 1.3 dev preview 케이스 매트릭스: text / block / button / form / file 의 모든 하위 변형.

import type { OriginalContent } from '../../../types/originalApi';

// --- text ---

export const textContentShort: OriginalContent = {
  content_type: 'text',
  payload: { text: '네, 확인 도와드리겠습니다.' },
};

export const textContentLong: OriginalContent = {
  content_type: 'text',
  payload: {
    text: [
      '안녕하세요, 문의 주셔서 감사합니다.',
      '말씀해주신 결제 오류 건은 현재 결제 대행사 점검으로 인해 일시적으로 발생한 것으로 확인됩니다.',
      '점검은 오늘 오후 6시경 완료될 예정이며, 완료 후 다시 시도해주시면 정상 결제가 가능합니다.',
      '이용에 불편을 드려 죄송하며, 추가 문의 사항이 있으시면 언제든 말씀해주세요.',
    ].join('\n'),
  },
};

// --- block ---

export const blockContentMarkdown: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      {
        block_type: 'text',
        text: '굵게 처리된 안내와 기울임 강조, 그리고 링크가 포함된 문단입니다.',
        markdown:
          '**굵게** 처리된 안내와 *기울임* 강조, 그리고 [도움말 링크](https://example.com/help)가 포함된 문단입니다.',
        raw_payload: { type: 'text' },
      },
    ],
  },
};

export const blockContentPlainText: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      {
        block_type: 'text',
        text: '마크다운 변환이 불필요한 평문 블록입니다. markdown 필드가 생략되어 text로 폴백합니다.',
        raw_payload: { type: 'text' },
      },
    ],
  },
};

export const blockContentCodeShort: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      {
        block_type: 'code',
        text: 'npm run build',
        label: 'bash',
        raw_payload: { language: 'bash' },
      },
    ],
  },
};

export const blockContentCodeLong: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      {
        block_type: 'code',
        label: 'typescript',
        text: [
          'export async function fetchOriginalContent(documentId: string) {',
          '  const response = await api.post("/api/v1/search/original", {',
          '    connector: "channel_talk",',
          '    document_id: documentId,',
          '  });',
          '  return response.data;',
          '}',
        ].join('\n'),
        raw_payload: { language: 'typescript' },
      },
    ],
  },
};

export const blockContentBullets: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      { block_type: 'bullets', text: '결제 내역 확인' },
      { block_type: 'bullets', text: '환불 정책 안내' },
      { block_type: 'bullets', text: '재결제 방법 설명' },
    ],
  },
};

export const blockContentMixed: OriginalContent = {
  content_type: 'block',
  payload: {
    blocks: [
      {
        block_type: 'text',
        text: '아래 명령어를 순서대로 실행해주세요.',
        markdown: '아래 명령어를 **순서대로** 실행해주세요.',
      },
      {
        block_type: 'code',
        label: 'bash',
        text: 'git pull origin develop\nnpm install',
        raw_payload: { language: 'bash' },
      },
      { block_type: 'bullets', text: '의존성 설치가 끝나면 dev 서버를 재시작합니다.' },
      { block_type: 'bullets', text: '문제가 계속되면 캐시를 삭제해주세요.' },
    ],
  },
};

// --- button ---

export const buttonContentSingle: OriginalContent = {
  content_type: 'button',
  payload: {
    buttons: [{ text: '결제 페이지로 이동', action: 'link', url: 'https://example.com/pay' }],
  },
};

export const buttonContentMultiple: OriginalContent = {
  content_type: 'button',
  payload: {
    buttons: [
      { text: '예, 맞습니다', action: 'submit', value: 'yes' },
      { text: '아니요', action: 'submit', value: 'no' },
      { text: '상담원 연결', action: 'link', url: 'https://example.com/agent' },
    ],
  },
};

// --- form ---

export const formContentVariedInputs: OriginalContent = {
  content_type: 'form',
  payload: {
    form: {
      form_type: 'profile',
      submitted_at: '2026-05-20T10:14:00+09:00',
      inputs: [
        { label: '플랜 선택', input_type: 'singleSelect', data_type: 'string', value: '엔터프라이즈' },
        { label: '뉴스레터 수신', input_type: 'bool', data_type: 'boolean', value: 'true' },
        { label: '회사명', input_type: 'text', data_type: 'string', value: '캐치업' },
        { label: '직원 수', input_type: 'number', data_type: 'number', value: '120' },
        { label: '도입 희망일', input_type: 'date', data_type: 'date', value: '2026-06-01' },
        {
          label: '데모 예약',
          input_type: 'datetime',
          data_type: 'datetime',
          value: '2026-05-28T14:00:00+09:00',
        },
        { label: '문의 경로', input_type: 'radio', data_type: 'string', value: '지인 추천' },
        { label: '관심 기능', input_type: 'checkbox', data_type: 'string', value: '검색, 원문 보기' },
        {
          label: '연동 도구',
          input_type: 'multiSelect',
          data_type: 'string',
          value: 'Slack, Jira, GitHub',
        },
      ],
    },
  },
};

export const formContentEmptyInputs: OriginalContent = {
  content_type: 'form',
  payload: {
    form: {
      form_type: 'survey',
      submitted_at: '2026-05-20T11:00:00+09:00',
      inputs: [],
    },
  },
};

// --- file ---

export const fileContentSingle: OriginalContent = {
  content_type: 'file',
  payload: {
    files: [
      {
        file_key: 'file-0001',
        name: '결제내역서.pdf',
        content_type: 'application/pdf',
        size: 248_120,
        url: 'https://example.com/files/payment-receipt.pdf',
      },
    ],
  },
};

export const fileContentMultiple: OriginalContent = {
  content_type: 'file',
  payload: {
    files: [
      {
        file_key: 'file-0002',
        name: '오류화면.png',
        content_type: 'image/png',
        size: 1_540_000,
        url: 'https://example.com/files/error-screen.png',
      },
      {
        file_key: 'file-0003',
        name: '로그_2026-05-20.txt',
        content_type: 'text/plain',
        size: 8_420,
        url: 'https://example.com/files/log.txt',
      },
      {
        file_key: 'file-0004',
        name: '계약서_최종.docx',
        content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        size: 92_300_000,
        url: 'https://example.com/files/contract.docx',
      },
    ],
  },
};
