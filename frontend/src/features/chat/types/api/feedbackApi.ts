/** 피드백 사유 리터럴 (백엔드 FeedbackLiteral StrEnum과 1:1) */
export type FeedbackReason =
  | 'HALLUCINATION'
  | 'OUTDATED'
  | 'NO_CITATION'
  | 'MISSING_INFO'
  | 'IRRELEVANT_SOURCE'
  | 'IRRELEVANT_ANSWER'
  | 'TOO_LONG'
  | 'OTHER';

/** 피드백 제출 요청 body */
export interface ChatFeedbackRequestApi {
  is_liked: boolean | null;
  reasons: FeedbackReason[];
  comment: string | null;
}

/** 피드백 제출 path params */
export interface ChatFeedbackPathParams {
  sessionId: string;
  messageId: string | number;
}

/** 피드백 mutation 전체 input */
export interface ChatFeedbackMutationInput {
  params: ChatFeedbackPathParams;
  body: ChatFeedbackRequestApi;
}

/** 피드백 제출 응답 */
export interface ChatFeedbackResponseApi {
  status: string;
  message_id: number;
  is_liked: boolean | null;
}
