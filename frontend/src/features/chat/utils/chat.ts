/**
 * Q&A 쌍 타입 정의
 */
export interface QAPair {
  question: Message;
  answer?: Message;
  index: number;
}

/**
 * 채팅 메시지 배열에서 질문/답변 쌍을 추출
 *
 * user 메시지를 기준으로 다음 assistant 메시지와 페어링
 * 하나의 user 메시지가 하나의 페이지가 됨
 */
export const extractQAPairs = (messages: Message[]): QAPair[] => {
  if (!messages || messages.length === 0) return [];

  const pairs: QAPair[] = [];

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role === 'user') {
      const nextMsg = messages[i + 1];
      pairs.push({
        question: msg,
        answer: nextMsg?.role === 'assistant' ? nextMsg : undefined,
        index: pairs.length,
      });
    }
  }

  return pairs;
};

/**
 * 문자열 정규화 (공백 통일)
 * 질문 검색/비교에 사용
 */
export const normalizeString = (s: string): string => {
  return s.replace(/\s+/g, ' ').trim();
};

/**
 * 질문으로 Q&A 페어의 인덱스 찾기
 */
export const findQAPairIndexByQuery = (qaPairs: QAPair[], query: string): number => {
  const normalizedQuery = normalizeString(query);
  return qaPairs.findIndex((p) => normalizeString(p.question.content) === normalizedQuery);
};
