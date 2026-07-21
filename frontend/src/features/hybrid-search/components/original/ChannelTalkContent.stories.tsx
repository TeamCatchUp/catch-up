'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import {
  blockContentBullets,
  blockContentCodeLong,
  blockContentCodeShort,
  blockContentMarkdown,
  blockContentMixed,
  blockContentPlainText,
  buttonContentMultiple,
  buttonContentSingle,
  fileContentMultiple,
  fileContentSingle,
  formContentEmptyInputs,
  formContentVariedInputs,
  textContentLong,
  textContentShort,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import BlockContent from '@/features/hybrid-search/components/original/channel-talk/contents/BlockContent';
import ButtonContent from '@/features/hybrid-search/components/original/channel-talk/contents/ButtonContent';
import FileContent from '@/features/hybrid-search/components/original/channel-talk/contents/FileContent';
import FormContent from '@/features/hybrid-search/components/original/channel-talk/contents/FormContent';
import TextContent from '@/features/hybrid-search/components/original/channel-talk/contents/TextContent';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  blockPayload,
  buttonPayload,
  Case,
  CHANNEL_TALK_STORY_DOCUMENT_ID,
  filePayload,
  formPayload,
  PanelWidth,
  StorySurface,
  textPayload,
} from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel/ChannelTalkContent',
  tags: ['autodocs'],
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
      dataNotes: ['Uses ChannelTalk original-content fixtures for text, block, button, form, and file payloads.'],
      reuseNotes: ['Renders production ChannelTalk content renderer leaf components.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const AllVariants: Story = {
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
            documentId={CHANNEL_TALK_STORY_DOCUMENT_ID}
          />
        </PanelWidth>
      </Case>
      <Case label="파일 여러 개">
        <PanelWidth>
          <FileContent
            content={filePayload(fileContentMultiple)}
            connector="channel_talk"
            documentId={CHANNEL_TALK_STORY_DOCUMENT_ID}
          />
        </PanelWidth>
      </Case>
    </StorySurface>
  ),
};
