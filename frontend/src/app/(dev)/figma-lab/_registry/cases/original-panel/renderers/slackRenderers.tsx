import type { ReactNode } from 'react';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import SlackThreadHeader from '@/features/hybrid-search/components/original/slack/header/SlackThreadHeader';
import SlackMessageItem from '@/features/hybrid-search/components/original/slack/message/SlackMessageItem';
import SlackOriginalPanelContent from '@/features/hybrid-search/components/original/slack/SlackOriginalPanelContent';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import Case from '../components/Case';
import type { OriginalPanelCaseId } from '../originalPanelEntries';

function SlackPanelWidth({ children }: { children: ReactNode }) {
  return <div className="w-99.75 max-w-full">{children}</div>;
}

export const slackRenderers = {
  'slack-thread-header': () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
    return (
      <Case label="Slack header">
        <SlackPanelWidth>
          <SlackThreadHeader channelName={thread.channelName} participantNames={thread.participantNames} />
        </SlackPanelWidth>
      </Case>
    );
  },
  'slack-message-item': () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
    return (
      <Case label="일반 메시지">
        <SlackPanelWidth>
          <SlackMessageItem message={thread.messages[0]} />
        </SlackPanelWidth>
      </Case>
    );
  },
  'slack-rich-message': () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
    return (
      <Case label="봇 rich 메시지">
        <SlackPanelWidth>
          <SlackMessageItem message={thread.messages[1]} />
        </SlackPanelWidth>
      </Case>
    );
  },
  'slack-panel-preview': () => (
    <Case label="Slack full panel">
      <SlackOriginalPanelContent
        pages={[slackOriginalThreadResponse]}
        hasNextPage={false}
        isFetchingNextPage={false}
        onLoadNextPage={() => undefined}
      />
    </Case>
  ),
} satisfies Partial<Record<OriginalPanelCaseId, () => ReactNode>>;
