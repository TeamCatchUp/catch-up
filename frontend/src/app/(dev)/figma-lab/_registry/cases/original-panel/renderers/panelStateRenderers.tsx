import type { ReactNode } from 'react';

import OriginalPanel from '@/features/hybrid-search/components/original/OriginalPanel';
import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';
import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/shared/states/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/shared/states/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/shared/states/OriginalPanelSkeleton';

import Case from '../components/Case';
import PanelFrame from '../components/PanelFrame';
import PanelWidth from '../components/PanelWidth';
import type { OriginalPanelCaseId } from '../originalPanelEntries';

export const panelStateRenderers = {
  'date-indicator': () => (
    <Case label="날짜 구분선">
      <PanelWidth>
        <DateIndicator date="2026-05-20T09:30:00+09:00" />
      </PanelWidth>
    </Case>
  ),
  'panel-skeleton': () => (
    <Case label="로딩 중">
      <PanelFrame>
        <OriginalPanelSkeleton />
      </PanelFrame>
    </Case>
  ),
  'panel-empty': () => (
    <Case label="선택된 문서 없음">
      <PanelFrame>
        <OriginalPanelEmpty />
      </PanelFrame>
    </Case>
  ),
  'panel-error': () => (
    <>
      <Case label="400 · 지원하지 않는 원문 유형">
        <PanelFrame>
          <OriginalPanelError message="지원하지 않는 원문 유형입니다" onRetry={() => {}} />
        </PanelFrame>
      </Case>
      <Case label="404 · 연동 정보 없음">
        <PanelFrame>
          <OriginalPanelError message="원문을 불러올 수 없어요 (연동 정보 없음)" onRetry={() => {}} />
        </PanelFrame>
      </Case>
      <Case label="422 · 제공처 오류">
        <PanelFrame>
          <OriginalPanelError message="원문 제공처에서 오류가 발생했어요" onRetry={() => {}} />
        </PanelFrame>
      </Case>
    </>
  ),
  'panel-coming-soon': () => (
    <>
      <Case label="Jira">
        <PanelFrame>
          <OriginalPanelComingSoon toolName="Jira" />
        </PanelFrame>
      </Case>
      <Case label="Github">
        <PanelFrame>
          <OriginalPanelComingSoon toolName="Github" />
        </PanelFrame>
      </Case>
      <Case label="Slack">
        <PanelFrame>
          <OriginalPanelComingSoon toolName="Slack" />
        </PanelFrame>
      </Case>
      <Case label="컨플루언스 위키 문서">
        <PanelFrame>
          <OriginalPanelComingSoon toolName="컨플루언스 위키 문서" />
        </PanelFrame>
      </Case>
      <Case label="채널톡 도큐먼트">
        <PanelFrame>
          <OriginalPanelComingSoon toolName="채널톡 도큐먼트" />
        </PanelFrame>
      </Case>
    </>
  ),
  panel: () => (
    <>
      <Case label="ComingSoon — connector='jira' (user_chat 아님)">
        <PanelFrame>
          <OriginalPanel connector="jira" entityType="issue" documentId="jira:issue:1" />
        </PanelFrame>
      </Case>
      <Case label="Empty — documentId=null (선택 문서 없음)">
        <PanelFrame>
          <OriginalPanel connector="channel_talk" entityType="user_chat" documentId={null} />
        </PanelFrame>
      </Case>
    </>
  ),
} satisfies Partial<Record<OriginalPanelCaseId, () => ReactNode>>;
