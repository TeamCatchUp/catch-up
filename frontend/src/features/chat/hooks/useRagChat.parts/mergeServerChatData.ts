import type { ChatData, Message } from '@/features/chat/types';

/**
 * 서버에서 받은 ChatData를 기존 prev에 부분 update 한다.
 *
 * 핵심 원칙: prev message id는 절대 바꾸지 않는다.
 * - streaming 중 부여한 UUID, 이전 hydrate에서 받은 server PK 모두 React key 안정성을 위해 보존.
 * - server entry → prev message 매칭으로 sources/메타만 patch.
 *
 * 매칭 알고리즘:
 * 1. 위치 매칭 우선 (대부분 1:1)
 * 2. content trim 매칭 fallback (위치 어긋남 edge case)
 * 3. server에 prev보다 많은 entry → 새 부분만 append
 * 4. prev에 server보다 많은 entry → 보존 (서버 커밋 지연 대응)
 */
export const mergeServerChatData = (prev: ChatData, serverData: ChatData): ChatData => {
  const { messages: serverMessages } = serverData;
  const { messages: prevMessages } = prev;

  const usedPrevIndices = new Set<number>();
  const merged: Message[] = [];

  for (let serverIdx = 0; serverIdx < serverMessages.length; serverIdx++) {
    const serverMsg = serverMessages[serverIdx];
    const prevAtSamePos = prevMessages[serverIdx];

    // 1. 위치 매칭: 같은 인덱스의 prev message가 같은 role이면 patch
    if (prevAtSamePos && prevAtSamePos.role === serverMsg.role && !usedPrevIndices.has(serverIdx)) {
      usedPrevIndices.add(serverIdx);
      merged.push(patchMessage(prevAtSamePos, serverMsg));
      continue;
    }

    // 2. content 매칭 fallback (위치 어긋남)
    const fallbackIdx = prevMessages.findIndex(
      (m, i) => !usedPrevIndices.has(i) && m.role === serverMsg.role && m.content.trim() === serverMsg.content.trim(),
    );
    if (fallbackIdx >= 0) {
      usedPrevIndices.add(fallbackIdx);
      merged.push(patchMessage(prevMessages[fallbackIdx], serverMsg));
      continue;
    }

    // 3. 매칭 없음: server entry 그대로 추가 (다른 클라이언트가 추가한 신규 entry)
    merged.push(serverMsg);
  }

  // 4. server보다 많은 prev entry 보존 (서버 커밋 지연 대응)
  for (let i = 0; i < prevMessages.length; i++) {
    if (!usedPrevIndices.has(i) && i >= serverMessages.length) {
      merged.push(prevMessages[i]);
    }
  }

  return {
    ...serverData,
    messages: merged,
  };
};

/**
 * prev message에 server message의 메타 필드만 patch한다.
 * - id는 절대 바꾸지 않음 (React key 안정)
 * - sources는 server 우선, 빈 배열이면 prev 보존 (서버 커밋 지연 시 streaming sources 보호)
 */
const patchMessage = (prevMsg: Message, serverMsg: Message): Message => {
  const serverHasSources = (serverMsg.sources?.length ?? 0) > 0;

  return {
    ...prevMsg,
    content: serverMsg.content || prevMsg.content,
    sources: serverHasSources ? serverMsg.sources : prevMsg.sources,
    chat_history_id: serverMsg.chat_history_id ?? prevMsg.chat_history_id,
    has_feedback: serverMsg.has_feedback ?? prevMsg.has_feedback,
    is_liked: serverMsg.is_liked ?? prevMsg.is_liked,
    is_saved: serverMsg.is_saved ?? prevMsg.is_saved,
    timestamp: serverMsg.timestamp || prevMsg.timestamp,
    // 스트림 종료 시 attach한 생성 과정 보존 — 서버 값 우선, 없으면 prev 유지
    pipeline_result: serverMsg.pipeline_result ?? prevMsg.pipeline_result,
  };
};
