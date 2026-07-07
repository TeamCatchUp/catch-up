'use client';

import type { ReactNode } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import {
  blockContentBullets,
  blockContentCodeLong,
  blockContentCodeShort,
  blockContentMarkdown,
  blockContentMixed,
  blockContentPlainText,
  buttonContentMultiple,
  buttonContentSingle,
  customerFull,
  customerPartial,
  emptyConversationResponse,
  fileContentMultiple,
  fileContentSingle,
  formContentEmptyInputs,
  formContentVariedInputs,
  fullConversationResponse,
  messageItemVariants,
  metadataVariants,
  textContentLong,
  textContentShort,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import ChannelTalkOriginalPanelContent from '@/features/hybrid-search/components/original/channel-talk/ChannelTalkOriginalPanelContent';
import BlockContent from '@/features/hybrid-search/components/original/channel-talk/contents/BlockContent';
import ButtonContent from '@/features/hybrid-search/components/original/channel-talk/contents/ButtonContent';
import FileContent from '@/features/hybrid-search/components/original/channel-talk/contents/FileContent';
import FormContent from '@/features/hybrid-search/components/original/channel-talk/contents/FormContent';
import TextContent from '@/features/hybrid-search/components/original/channel-talk/contents/TextContent';
import Collapsible from '@/features/hybrid-search/components/original/channel-talk/metadata/Collapsible';
import ConsultationInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/ConsultationInfo';
import CustomerInfo from '@/features/hybrid-search/components/original/channel-talk/metadata/CustomerInfo';
import MessageItem from '@/features/hybrid-search/components/original/channel-talk/timeline/MessageItem';
import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';
import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/shared/states/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/shared/states/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/shared/states/OriginalPanelSkeleton';
import SlackThreadHeader from '@/features/hybrid-search/components/original/slack/header/SlackThreadHeader';
import SlackMessageItem from '@/features/hybrid-search/components/original/slack/message/SlackMessageItem';
import SlackOriginalPanelContent from '@/features/hybrid-search/components/original/slack/SlackOriginalPanelContent';
import type {
  OriginalBlockPayload,
  OriginalButtonPayload,
  OriginalContent,
  OriginalFilePayload,
  OriginalFormPayload,
  OriginalTextPayload,
} from '@/features/hybrid-search/types/originalApi';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import OriginalPanel from './OriginalPanel';

interface OriginalPanelStoryArgs {
  onRetry: () => void;
}

function textPayload(content: OriginalContent): OriginalTextPayload {
  if (content.content_type !== 'text') throw new Error('expected text content');
  return content.payload;
}

function blockPayload(content: OriginalContent): OriginalBlockPayload {
  if (content.content_type !== 'block') throw new Error('expected block content');
  return content.payload;
}

function buttonPayload(content: OriginalContent): OriginalButtonPayload {
  if (content.content_type !== 'button') throw new Error('expected button content');
  return content.payload;
}

function formPayload(content: OriginalContent): OriginalFormPayload {
  if (content.content_type !== 'form') throw new Error('expected form content');
  return content.payload;
}

function filePayload(content: OriginalContent): OriginalFilePayload {
  if (content.content_type !== 'file') throw new Error('expected file content');
  return content.payload;
}

function StorySurface({ children }: { children: ReactNode }) {
  return <div className="bg-fill-normal-normal flex min-h-full flex-col gap-6 p-6">{children}</div>;
}

function Case({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body-xsmall text-text-normal-assistive font-medium">{label}</span>
      {children}
    </div>
  );
}

function PanelWidth({ children }: { children: ReactNode }) {
  return <div className="bg-fill-normal-strong border-line-normal-neutral w-90 rounded-xl border p-3">{children}</div>;
}

function PanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-normal-strong border-line-normal-neutral h-160 w-90 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}

function SlackPanelWidth({ children }: { children: ReactNode }) {
  return <div className="w-99.75 max-w-full">{children}</div>;
}

function SlackPanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-normal-strong border-line-normal-neutral h-160 w-120 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel',
  tags: ['autodocs'],
  args: {
    onRetry: fn(),
  },
  argTypes: {
    onRetry: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'original-panel',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['contents', 'messages', 'metadata', 'panel-states', 'slack', 'assembled'],
      dataNotes: [
        'Stories reuse production original-panel fixtures from components/original/__fixtures__.',
        'Container-state story only uses disabled-query states, so it does not need API handlers.',
      ],
      reuseNotes: [
        'ChannelTalk stories render production content, metadata, timeline, and state components.',
        'Slack stories render production Slack header, message item, and full panel content components.',
      ],
    }),
  },
} satisfies Meta<OriginalPanelStoryArgs>;

export default meta;

type Story = StoryObj<OriginalPanelStoryArgs>;

export const ChannelTalkContents: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'text-content',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['text-content', 'block-content', 'button-content', 'form-content', 'file-content'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="짧은 텍스트">
        <PanelWidth>
          <TextContent content={textPayload(textContentShort)} />
        </PanelWidth>
      </Case>
      <Case label="긴 텍스트">
        <PanelWidth>
          <TextContent content={textPayload(textContentLong)} />
        </PanelWidth>
      </Case>
      <Case label="마크다운 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentMarkdown)} />
        </PanelWidth>
      </Case>
      <Case label="평문 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentPlainText)} />
        </PanelWidth>
      </Case>
      <Case label="짧은 코드 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentCodeShort)} />
        </PanelWidth>
      </Case>
      <Case label="긴 코드 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentCodeLong)} />
        </PanelWidth>
      </Case>
      <Case label="불릿 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentBullets)} />
        </PanelWidth>
      </Case>
      <Case label="혼합 블록">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentMixed)} />
        </PanelWidth>
      </Case>
      <Case label="버튼 1개">
        <PanelWidth>
          <ButtonContent content={buttonPayload(buttonContentSingle)} />
        </PanelWidth>
      </Case>
      <Case label="버튼 여러 개">
        <PanelWidth>
          <ButtonContent content={buttonPayload(buttonContentMultiple)} />
        </PanelWidth>
      </Case>
      <Case label="폼 다양한 입력">
        <PanelWidth>
          <FormContent content={formPayload(formContentVariedInputs)} />
        </PanelWidth>
      </Case>
      <Case label="폼 빈 입력">
        <PanelWidth>
          <FormContent content={formPayload(formContentEmptyInputs)} />
        </PanelWidth>
      </Case>
      <Case label="파일 1개">
        <PanelWidth>
          <FileContent
            content={filePayload(fileContentSingle)}
            connector="channel_talk"
            documentId="channel_talk:user_chat:storybook-fixture"
          />
        </PanelWidth>
      </Case>
      <Case label="파일 여러 개">
        <PanelWidth>
          <FileContent
            content={filePayload(fileContentMultiple)}
            connector="channel_talk"
            documentId="channel_talk:user_chat:storybook-fixture"
          />
        </PanelWidth>
      </Case>
    </StorySurface>
  ),
};

export const ChannelTalkMessages: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'message-item',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['message-item', 'date-indicator'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="날짜 구분선">
        <PanelWidth>
          <DateIndicator date="2026-05-20T09:30:00+09:00" />
        </PanelWidth>
      </Case>
      {messageItemVariants.map((variant) => (
        <Case key={variant.item.id} label={variant.label}>
          <PanelWidth>
            <MessageItem
              item={variant.item}
              connector="channel_talk"
              documentId="channel_talk:user_chat:storybook-fixture"
            />
          </PanelWidth>
        </Case>
      ))}
    </StorySurface>
  ),
};

export const ChannelTalkInfo: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'consultation-info',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['consultation-info', 'customer-info', 'collapsible'],
    }),
  },
  render: () => (
    <StorySurface>
      {metadataVariants.map((variant) => (
        <Case key={variant.metadata.user_chat_id} label={variant.label}>
          <PanelWidth>
            <ConsultationInfo metadata={variant.metadata} />
          </PanelWidth>
        </Case>
      ))}
      <Case label="고객 정보 전체 필드">
        <PanelWidth>
          <CustomerInfo customer={customerFull} />
        </PanelWidth>
      </Case>
      <Case label="고객 정보 일부 필드">
        <PanelWidth>
          <CustomerInfo customer={customerPartial} />
        </PanelWidth>
      </Case>
      <Case label="고객 정보 없음">
        <PanelWidth>
          <CustomerInfo customer={undefined} />
        </PanelWidth>
      </Case>
      <Case label="접기 펼치기">
        <PanelWidth>
          <Collapsible
            open
            onOpenChange={() => undefined}
            header={<span className="text-body-small text-text-normal-normal py-2 font-medium">펼쳐진 헤더</span>}
          >
            <p className="text-body-small text-text-normal-alternative pb-2">접히는 본문 영역입니다.</p>
          </Collapsible>
        </PanelWidth>
      </Case>
    </StorySurface>
  ),
};

export const PanelStates: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      figmaLab: {
        caseId: 'panel-skeleton',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['panel-skeleton', 'panel-empty', 'panel-error', 'panel-coming-soon'],
      interactionNotes: ['Actions log retry clicks from OriginalPanelError variants.'],
    }),
  },
  render: ({ onRetry }) => (
    <StorySurface>
      <Case label="로딩 중">
        <PanelFrame>
          <OriginalPanelSkeleton />
        </PanelFrame>
      </Case>
      <Case label="선택된 문서 없음">
        <PanelFrame>
          <OriginalPanelEmpty />
        </PanelFrame>
      </Case>
      <Case label="400 지원하지 않는 원문 유형">
        <PanelFrame>
          <OriginalPanelError message="지원하지 않는 원문 유형입니다" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      <Case label="404 연동 정보 없음">
        <PanelFrame>
          <OriginalPanelError message="원문을 불러올 수 없어요 (연동 정보 없음)" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      <Case label="422 제공처 오류">
        <PanelFrame>
          <OriginalPanelError message="원문 제공처에서 오류가 발생했어요" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      {['Jira', 'Github', 'Slack', '컨플루언스 위키 문서', '채널톡 도큐먼트'].map((toolName) => (
        <Case key={toolName} label={`준비 중 ${toolName}`}>
          <PanelFrame>
            <OriginalPanelComingSoon toolName={toolName} />
          </PanelFrame>
        </Case>
      ))}
    </StorySurface>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getAllByRole('button', { name: '다시 시도' })[0]);
    await expect(args.onRetry).toHaveBeenCalled();
  },
};

export const SlackMessages: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-message-item',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['slack-thread-header', 'slack-message-item', 'slack-rich-message'],
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14427-58787&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14427:58787',
      },
    }),
  },
  render: () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);

    return (
      <StorySurface>
        <Case label="Slack header">
          <SlackPanelWidth>
            <SlackThreadHeader channelName={thread.channelName} participantNames={thread.participantNames} />
          </SlackPanelWidth>
        </Case>
        <Case label="일반 메시지">
          <SlackPanelWidth>
            <SlackMessageItem message={thread.messages[0]} />
          </SlackPanelWidth>
        </Case>
        <Case label="봇 rich 메시지">
          <SlackPanelWidth>
            <SlackMessageItem message={thread.messages[1]} />
          </SlackPanelWidth>
        </Case>
      </StorySurface>
    );
  },
};

export const AssembledPanels: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-panel-preview',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['panel-content', 'slack-panel-preview'],
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14152-56488&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14152:56488',
      },
      viewport: {
        width: 520,
        height: 760,
      },
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="현실적인 전체 대화">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={fullConversationResponse} />
        </PanelFrame>
      </Case>
      <Case label="메시지 0건">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={emptyConversationResponse} />
        </PanelFrame>
      </Case>
      <Case label="Slack full panel">
        <SlackPanelFrame>
          <SlackOriginalPanelContent
            pages={[slackOriginalThreadResponse]}
            hasNextPage={false}
            isFetchingNextPage={false}
            onLoadNextPage={() => undefined}
          />
        </SlackPanelFrame>
      </Case>
    </StorySurface>
  ),
};

export const ContainerStates: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      figmaLab: {
        caseId: 'panel',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['coming-soon-container', 'empty-container'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="ComingSoon connector=jira">
        <PanelFrame>
          <OriginalPanel connector="jira" entityType="issue" documentId="jira:issue:1" />
        </PanelFrame>
      </Case>
      <Case label="Empty documentId=null">
        <PanelFrame>
          <OriginalPanel connector="channel_talk" entityType="user_chat" documentId={null} />
        </PanelFrame>
      </Case>
    </StorySurface>
  ),
};
