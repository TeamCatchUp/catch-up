import type { Message } from '@/features/chat/types';

/**
 * 질문/답변 쌍 타입
 *
 * 채팅 UI에서 Q&A 단위로 메시지를 표시하기 위한 구조
 */
export interface QAPair {
  question: Message; // user 메시지
  answer?: Message; // 다음 assistant 메시지 (없을 수 있음)
  index: number; // 페어 인덱스 (0부터 시작)
}

/**
 * 채팅 메시지 배열에서 질문/답변 쌍을 추출
 *
 * user 메시지를 기준으로 다음 assistant 메시지와 페어링
 * - 하나의 user 메시지 = 하나의 QAPair
 * - 연속된 assistant 메시지가 있으면 마지막 것을 답변으로 사용
 * - answer가 없는 경우도 허용 (질문만 있고 답변 없음)
 *
 * @param messages - 전체 메시지 배열
 * @returns Q&A 쌍 배열
 */
export const extractQAPairs = (messages: Message[]): QAPair[] => {
  if (!messages || messages.length === 0) return [];

  const pairs: QAPair[] = [];

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role === 'user') {
      let nextMsg: Message | undefined;
      for (let j = i + 1; j < messages.length; j++) {
        const candidate = messages[j];
        if (candidate.role === 'user') break;
        if (candidate.role === 'assistant') {
          // 여러 개의 assistant 메시지가 연속된 경우 마지막 것을 유효한 답변으로 사용
          nextMsg = candidate;
        }
      }

      pairs.push({
        question: msg,
        answer: nextMsg,
        index: pairs.length,
      });
    }
  }

  return pairs;
};

/**
 * 문자열 정규화 (연속 공백을 단일 공백으로 통일)
 *
 * 질문 검색/비교 시 공백 차이를 무시하기 위해 사용
 *
 * @param s - 정규화할 문자열
 * @returns 정규화된 문자열
 */
export const normalizeString = (s: string): string => {
  return s.replace(/\s+/g, ' ').trim();
};

/**
 * 질문 내용으로 Q&A 페어의 인덱스 찾기
 *
 * 공백을 정규화한 후 정확히 일치하는 질문 검색
 *
 * @param qaPairs - Q&A 쌍 배열
 * @param query - 검색할 질문 내용
 * @returns 일치하는 페어의 인덱스 또는 -1
 */
export const findQAPairIndexByQuery = (qaPairs: QAPair[], query: string): number => {
  const normalizedQuery = normalizeString(query);
  return qaPairs.findIndex((p) => normalizeString(p.question.content) === normalizedQuery);
};
