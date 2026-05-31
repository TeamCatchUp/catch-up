'use client';

// 원문 패널 컨테이너 — connector/entityType/documentId 로 상태 분기.
// 현재 ChannelTalk user_chat과 Slack message만 실제 원문 API를 연결한다.

import { isAxiosError } from 'axios';

import ChannelTalkOriginalPanelContent from '@/features/hybrid-search/components/original/channel-talk/ChannelTalkOriginalPanelContent';
import SlackOriginalPanelContent from '@/features/hybrid-search/components/original/slack/SlackOriginalPanelContent';
import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/shared/states/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/shared/states/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/shared/states/OriginalPanelSkeleton';
import {
  useOriginalContent,
  useSlackOriginalContentInfinite,
} from '@/features/hybrid-search/hooks/useOriginalContent';
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

function isSlackMessage(connector: SourceTypeApi | null, entityType: string | null): boolean {
  return connector === 'slack' && entityType === 'message';
}

// Coming Soon 카피의 협업 툴 표시명 — connector/entityType 매핑 테이블.
function resolveToolName(connector: SourceTypeApi | null, entityType: string | null): string {
  if (connector === 'channel_talk' && entityType === 'document_article') return '채널톡 도큐먼트';
  if (connector === null || connector === 'unknown') return '해당 도구';
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
    default: {
      // SourceTypeApi 에 새 connector 추가 시 컴파일 실패 — 위 switch 도 갱신해야 함.
      const _exhaustive: never = connector;
      return _exhaustive;
    }
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
  const params = {
    connector: connector ?? 'unknown',
    entityType: entityType ?? '',
    documentId: documentId ?? '',
  };
  const channelTalkQuery = useOriginalContent(params);
  const slackQuery = useSlackOriginalContentInfinite(params);

  // (a) 선택된 문서가 없음 — 빈 상태 (검색 전·결과 0건 포함).
  // isUserChat 보다 먼저 체크 — connector/entityType 가 모두 null 일 때 잘못 ComingSoon 으로 빠지는 것 방지.
  if (documentId == null) {
    return <OriginalPanelEmpty />;
  }

  if (isUserChat(connector, entityType)) {
    if (channelTalkQuery.isLoading) {
      return <OriginalPanelSkeleton />;
    }

    if (channelTalkQuery.isError) {
      return (
        <OriginalPanelError
          message={resolveErrorMessage(channelTalkQuery.error)}
          onRetry={() => void channelTalkQuery.refetch()}
        />
      );
    }

    if (channelTalkQuery.isSuccess) {
      return <ChannelTalkOriginalPanelContent data={channelTalkQuery.data} />;
    }

    return <OriginalPanelSkeleton />;
  }

  if (isSlackMessage(connector, entityType)) {
    if (slackQuery.isLoading) {
      return <OriginalPanelSkeleton />;
    }

    if (slackQuery.isError) {
      return (
        <OriginalPanelError
          message={resolveErrorMessage(slackQuery.error)}
          onRetry={() => void slackQuery.refetch()}
        />
      );
    }

    if (slackQuery.isSuccess) {
      return (
        <SlackOriginalPanelContent
          pages={slackQuery.data.pages}
          hasNextPage={Boolean(slackQuery.hasNextPage)}
          isFetchingNextPage={slackQuery.isFetchingNextPage}
          onLoadNextPage={() => void slackQuery.fetchNextPage()}
        />
      );
    }

    return <OriginalPanelSkeleton />;
  }

  return <OriginalPanelComingSoon toolName={resolveToolName(connector, entityType)} />;
}
