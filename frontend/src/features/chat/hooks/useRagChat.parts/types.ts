import type { Dispatch, RefObject, SetStateAction } from 'react';

import type {
  ChatData,
  ChatSource,
  PipelineQueryType,
  SourceResponse,
  StepRow,
} from '@/features/chat/types';

/**
 * useRagChat 입력 파라미터
 * - `sessionId`: URL path parameter (`/chat/{sessionId}`)
 * - `repo`: 선택된 저장소 필터(없을 수 있음)
 * - `initialQuery`: URL `?q=`로 전달되는 첫 질문
 */
export interface UseRagChatOptions {
  sessionId: string;
  repo: string | null;
  initialQuery: string | null;
  scrollToMessageId?: string | null;
  toolFilters?: string[];
}

/**
 * useRagChat 반환값
 * - UI 렌더링 상태 + 사용자 액션 핸들러를 묶어 노출
 */
export interface UseRagChatReturn {
  chatData: ChatData | null;
  resolvedSessionId: string | undefined;
  isLoading: boolean;
  isError: boolean;
  /** 답변 생성 과정 step rows (스트림 중 누적, 종료 시 화면에서 unmount) */
  stepRows: StepRow[];
  /** supervisor가 결정한 파이프라인 분류 (RagAnswerSkeleton 마운트 게이트) */
  pipelineQueryType: PipelineQueryType | null;
  /** supervisor가 추출한 질문 topic (TopicHeader) */
  topic: string | null;
  /** supervisor reasoning (PipelineTypeBanner 멘트) */
  pipelineReasoning: string | null;
  sendMessage: (message: string) => Promise<void>;
  submitEdit: (messageId: string, newContent: string) => Promise<void>;
  handleStop: () => void;
  setChatData: Dispatch<SetStateAction<ChatData | null>>;
  updateMessageFeedback: (messageId: string, isLiked: boolean | undefined) => void;

  // 역방향 무한 스크롤
  hasOlderMessages: boolean;
  isLoadingOlderMessages: boolean;
  loadPreviousMessages: () => Promise<void>;
}

/**
 * 세션 전환 제어용 ref 묶음
 *
 * 왜 ref를 쓰는가?
 * - session 전환 중에는 "렌더링 state"보다 "동기적인 플래그"가 중요하다.
 * - replace/hydrate 중복 실행 방지 가드는 render와 분리된 안정적인 저장소가 필요하다.
 */
export interface SessionGuardRefs {
  // 마지막으로 동기화했던 sessionId
  syncedSessionRef: RefObject<string | null>;
  // replace 직후 1회성 guard (from -> to)
  sessionSyncGuardRef: RefObject<{ from: string; to: string } | null>;
  // 스트림에서 수신한 임시 sessionId 보관
  pendingReplaceSessionIdRef: RefObject<string | null>;
  // placeholder replace를 이미 수행했는지
  hasPlaceholderReplacedRef: RefObject<boolean>;
  // "스트림이 정상 종료되기 전에는 replace 금지" 가드
  canReplacePlaceholderRef: RefObject<boolean>;
}

/**
 * 스트림 런타임 제어용 ref 묶음
 *
 * 공통 원칙:
 * - 토큰 단위 이벤트가 빠르게 들어오므로 state보다 ref가 유리
 * - 이벤트 핸들러 클로저가 stale되지 않도록 최신 값을 ref로 보관
 */
export interface StreamRuntimeRefs {
  // 현재 토큰이 append되고 있는 assistant message id
  streamingMessageIdRef: RefObject<string | null>;
  // token 이벤트를 한 번이라도 받았는지
  hasStreamedTokenRef: RefObject<boolean>;
  // 최근 sources(raw) 캐시
  latestSourcesRef: RefObject<SourceResponse[]>;
  // 최근 sources(ui normalized) 캐시
  latestUiSourcesRef: RefObject<ChatSource[]>;
  // 현재 스트림 요청이 진행 중인지
  streamInFlightRef: RefObject<boolean>;
  // URL `?q` 기반 자동 스트림을 이미 시도했는지
  hasAttemptedInitialStreamRef: RefObject<boolean>;
  // finalize 시점에 참조할 최신 resolvedSessionId
  resolvedSessionIdRef: RefObject<string | undefined>;
}

/**
 * useRagChat 내부에서 여러 part 훅이 공통으로 쓰는 state setter 집합.
 * - 각 part 훅이 필요한 setter만 직접 파라미터로 받지 않게 하여 시그니처를 단순화
 */
export interface ChatStateSetters {
  setChatData: Dispatch<SetStateAction<ChatData | null>>;
  setIsLoading: Dispatch<SetStateAction<boolean>>;
  setIsError: Dispatch<SetStateAction<boolean>>;
  setStepRows: Dispatch<SetStateAction<StepRow[]>>;
  setPipelineQueryType: Dispatch<SetStateAction<PipelineQueryType | null>>;
  setTopic: Dispatch<SetStateAction<string | null>>;
  setPipelineReasoning: Dispatch<SetStateAction<string | null>>;
}
