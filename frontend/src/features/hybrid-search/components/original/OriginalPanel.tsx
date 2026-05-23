'use client';

// 원문 패널 컨테이너 — connector/entityType/documentId 로 상태 분기.
// user_chat 이 아니면 Coming Soon (fetch 안 함), 그 외엔 useOriginalContent 결과로 분기.

import { isAxiosError } from 'axios';

import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/OriginalPanelComingSoon';
import OriginalPanelContent from '@/features/hybrid-search/components/original/OriginalPanelContent';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/OriginalPanelSkeleton';
import { useOriginalContent } from '@/features/hybrid-search/hooks/useOriginalContent';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

interface OriginalPanelProps {
  connector: SourceTypeApi | null;
  entityType: string | null;
  documentId: string | null;
}

// 선택된 소스가 ChannelTalk user_chat 인지 — 이때만 실제 원문 패널을 띄운다.
function isUserChat(connector: SourceTypeApi | null, entityType: string | null): boolean {
  return connector === 'channel_talk' && entityType === 'user_chat';
}

// Coming Soon 카피의 협업 툴 표시명 — connector/entityType 매핑 테이블.
function resolveToolName(connector: SourceTypeApi | null, entityType: string | null): string {
  if (connector === 'channel_talk' && entityType === 'document_article') return '채널톡 도큐먼트';
  switch (connector) {
    case 'confluence':
      return '컨플루언스 위키 문서';
    case 'github':
      return 'Github';
    case 'slack':
      return 'Slack';
    case 'jira':
      return 'Jira';
    case 'channel_talk':
      return '채널톡';
    default:
      return '해당 도구';
  }
}

// HTTP status → 사용자용 한국어 에러 메시지.
function resolveErrorMessage(error: unknown): string {
  const status = isAxiosError(error) ? error.response?.status : undefined;
  switch (status) {
    case 400:
      return '지원하지 않는 원문 유형입니다';
    case 404:
      return '원문을 불러올 수 없어요 (연동 정보 없음)';
    case 422:
      return '원문 제공처에서 오류가 발생했어요';
    default:
      return '원문을 불러오는 중 문제가 발생했어요';
  }
}

export default function OriginalPanel({ connector, entityType, documentId }: OriginalPanelProps) {
  // user_chat 이 아니면 query 가 disabled — connector/documentId 폴백은 호출만을 위한 값.
  const query = useOriginalContent({
    connector: connector ?? 'unknown',
    entityType: entityType ?? '',
    documentId: documentId ?? '',
  });

  // (a) 선택된 문서가 없음 — 빈 상태 (검색 전·결과 0건 포함).
  // isUserChat 보다 먼저 체크 — connector/entityType 가 모두 null 일 때 잘못 ComingSoon 으로 빠지는 것 방지.
  if (documentId == null) {
    return <OriginalPanelEmpty />;
  }

  // (b) ChannelTalk user_chat 이 아닌 선택 — 준비 중 안내.
  if (!isUserChat(connector, entityType)) {
    return <OriginalPanelComingSoon toolName={resolveToolName(connector, entityType)} />;
  }

  // (c) 로딩 중.
  if (query.isLoading) {
    return <OriginalPanelSkeleton />;
  }

  // (d) 에러 — HTTP status 별 메시지 + 재시도.
  if (query.isError) {
    return <OriginalPanelError message={resolveErrorMessage(query.error)} onRetry={query.refetch} />;
  }

  // (e) 성공.
  if (query.isSuccess) {
    return <OriginalPanelContent data={query.data} />;
  }

  return <OriginalPanelSkeleton />;
}
