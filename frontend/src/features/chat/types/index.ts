/**
 * Chat feature 타입 진입점.
 * - api/model/props 하위 타입을 재노출
 * - 기존 코드 호환을 위한 별칭 타입 제공
 */
export * from '@/features/chat/types/api/feedbackApi';
export * from '@/features/chat/types/api/sourceApi';
export * from '@/features/chat/types/api/streamApi';
export * from '@/features/chat/types/model/chatModel';
export * from '@/features/chat/types/model/stepModel';
export * from '@/features/chat/types/model/taskModel';
export * from '@/features/chat/types/props/actionProps';

/** 호환용 별칭: 소스 플랫폼 타입 */
export type SourceType = import('@/features/chat/types/api/sourceApi').SourceTypeApi;
/** 호환용 별칭: 소스 엔티티 타입 */
export type EntityType = import('@/features/chat/types/api/sourceApi').EntityTypeApi;
/** 호환용 별칭: 소스 응답 타입 */
export type SourceResponse = import('@/features/chat/types/api/sourceApi').SourceResponseApi;

/** 기존 코드 호환용 별칭: 출처 모델 */
export type ChatSource = import('@/features/chat/types/model/chatModel').ChatSourceModel;
/** 기존 코드 호환용 별칭: Jira 서브태스크 모델 */
export type JiraSubTask = import('@/features/chat/types/model/chatModel').JiraSubTaskModel;
/** 기존 코드 호환용 별칭: Jira 태스크 모델 */
export type JiraTask = import('@/features/chat/types/model/chatModel').JiraTaskModel;
/** 기존 코드 호환용 별칭: 메시지 모델 */
export type Message = import('@/features/chat/types/model/chatModel').MessageModel;
/** 기존 코드 호환용 별칭: 채팅 데이터 모델 */
export type ChatData = import('@/features/chat/types/model/chatModel').ChatDataModel;

/** 기존 코드 호환용 별칭: 전체 RAG 단계 키 */
export type RagStepKey = import('@/features/chat/types/model/stepModel').RagStepKeyModel;
/** 기존 코드 호환용 별칭: UI RAG 단계 키 */
export type RagUIStepKey = import('@/features/chat/types/model/stepModel').RagUIStepKeyModel;

/** 기존 코드 호환용 별칭: 단순 서브태스크 모델 */
export type SubTask = import('@/features/chat/types/model/taskModel').SubTaskModel;
/** 기존 코드 호환용 별칭: 단순 태스크 모델 */
export type Task = import('@/features/chat/types/model/taskModel').TaskModel;

/** 기존 코드 호환용 별칭: 피드백 요청 API */
export type ChatFeedbackRequest = import('@/features/chat/types/api/feedbackApi').ChatFeedbackRequestApi;
/** 기존 코드 호환용 별칭: 피드백 응답 API */
export type ChatFeedbackResponse = import('@/features/chat/types/api/feedbackApi').ChatFeedbackResponseApi;
/** 기존 코드 호환용 별칭: 스트림 이벤트 API */
export type StreamEvent = import('@/features/chat/types/api/streamApi').StreamEventApi;
