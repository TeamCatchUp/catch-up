// ChatSourceModel은 shared/types/ragSourceModel로 승격됨 (chat + hybrid-search 공유).
// 본 파일은 backward-compat alias만 유지.

import type { PipelineEventApi } from '@/features/chat/types/api/streamApi';
import type { RagSourceTypeModel, RagSourceUiModel } from '@/shared/types/ragSourceModel';

/** @deprecated shared의 RagSourceTypeModel을 직접 import 권장. */
export type ChatSourceTypeModel = RagSourceTypeModel;

/** @deprecated shared의 RagSourceUiModel을 직접 import 권장. */
export type ChatSourceModel = RagSourceUiModel;

export interface MessageModel {
  id: string;
  chat_history_id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSourceModel[];
  timestamp: string;
  has_feedback?: boolean;
  is_liked?: boolean;
  is_saved?: boolean;
  // RAG 답변 생성 과정. assistant 메시지에만. 스트림 종료 시 누적분 attach 또는 히스토리 매핑.
  pipeline_result?: PipelineEventApi[] | null;
}

export interface ChatDataModel {
  session_id: string;
  title: string;
  repo: string;
  messages: MessageModel[];
}
