// RAG 출처 UI 모델 — chat sidebar + hybrid-search 결과 카드 양쪽에서 공유.
// SourceResponseApi(snake_case API)를 normalizeRagSources로 매핑한 UI 친화 shape.

import type { EntityTypeApi, SourceTypeApi } from '@/shared/types/sourceApi';

/** 백엔드 SourceType과 동일 */
export type RagSourceTypeModel = SourceTypeApi;

/** 답변 사이드바·검색 결과 양쪽에서 사용하는 출처 모델. */
export interface RagSourceUiModel {
  id: string;
  source_type: RagSourceTypeModel;
  entity_type: EntityTypeApi;
  is_cited: boolean;
  repo: string;
  title: string;
  content: string;
  date: string;
  author: string;
  html_url: string;
  source_index: number;
  /** Jira 이슈키 (예: "CAT-297") */
  issue_key?: string;
  /** GitHub PR/Issue 번호 */
  github_number?: number;
}
