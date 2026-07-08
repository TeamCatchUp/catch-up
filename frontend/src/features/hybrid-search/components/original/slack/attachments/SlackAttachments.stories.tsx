'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import type { SlackAttachmentRaw, SlackFileRaw } from '@/features/hybrid-search/types/slackOriginalApi';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelWidth, StorySurface } from '../../OriginalPanelStoryFrame';
import SlackFileAttachment from './SlackFileAttachment';
import SlackLinkPreview from './SlackLinkPreview';

const fileAttachment: SlackFileRaw = {
  id: 'storybook-file',
  name: 'slack-original-panel-specification-with-long-name.pdf',
  title: 'slack-original-panel-specification-with-long-name.pdf',
  mimetype: 'application/pdf',
  size: 153600,
  permalink: 'https://catchup.slack.com/files/storybook-file',
};

const imageFallbackFile: SlackFileRaw = {
  id: 'storybook-image-without-thumb',
  name: 'fallback-image-without-thumb.png',
  title: 'fallback-image-without-thumb.png',
  mimetype: 'image/png',
  size: 1024,
  permalink: 'https://catchup.slack.com/files/storybook-image-without-thumb',
};

const linkPreview: SlackAttachmentRaw = {
  id: 1,
  title: 'Slack 원문 패널 링크 프리뷰 제목이 길어질 때',
  title_link: 'https://example.com/slack-original-panel',
  text: '링크 설명이 길어져도 한 줄에서 안정적으로 잘립니다.',
  image_url: 'https://placehold.co/560x240/png?text=Preview',
  from_url: 'https://example.com/slack-original-panel',
};

const meta = {
  title: 'Compositions/Hybrid Search/Original/SlackAttachments',
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-attachments',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['file-row', 'image-file-fallback', 'link-preview', 'safe-url'],
      viewport: {
        width: 520,
        height: 680,
      },
      dataNotes: ['Covers Slack file rows and link previews with long names, metadata, and safe URLs.'],
      reuseNotes: ['Covers attachment units before they are embedded in SlackMessageBody.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const AttachmentVariants: Story = {
  render: () => (
    <StorySurface>
      <Case label="파일 row">
        <SlackPanelWidth>
          <SlackFileAttachment file={fileAttachment} originalUrl="https://catchup.slack.com/archives/C00000001" />
        </SlackPanelWidth>
      </Case>
      <Case label="이미지 thumb 없음">
        <SlackPanelWidth>
          <SlackFileAttachment file={imageFallbackFile} originalUrl={null} />
        </SlackPanelWidth>
      </Case>
      <Case label="링크 프리뷰">
        <SlackPanelWidth>
          <SlackLinkPreview attachment={linkPreview} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  ),
};
