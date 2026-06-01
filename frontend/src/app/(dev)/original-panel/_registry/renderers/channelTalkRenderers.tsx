import type { ReactNode } from 'react';

import {
  blockContentBullets,
  blockContentCodeLong,
  blockContentCodeShort,
  blockContentMarkdown,
  blockContentMixed,
  blockContentPlainText,
  buttonContentMultiple,
  buttonContentSingle,
  emptyConversationResponse,
  fileContentMultiple,
  fileContentSingle,
  formContentEmptyInputs,
  formContentVariedInputs,
  fullConversationResponse,
  messageItemVariants,
  textContentLong,
  textContentShort,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import ChannelTalkOriginalPanelContent from '@/features/hybrid-search/components/original/channel-talk/ChannelTalkOriginalPanelContent';
import BlockContent from '@/features/hybrid-search/components/original/channel-talk/contents/BlockContent';
import ButtonContent from '@/features/hybrid-search/components/original/channel-talk/contents/ButtonContent';
import FileContent from '@/features/hybrid-search/components/original/channel-talk/contents/FileContent';
import FormContent from '@/features/hybrid-search/components/original/channel-talk/contents/FormContent';
import TextContent from '@/features/hybrid-search/components/original/channel-talk/contents/TextContent';
import MessageItem from '@/features/hybrid-search/components/original/channel-talk/timeline/MessageItem';

import Case from '../../_components/Case';
import PanelFrame from '../../_components/PanelFrame';
import PanelWidth from '../../_components/PanelWidth';
import type { EntrySlug } from '../entries';
import { blockPayload, buttonPayload, filePayload, formPayload, textPayload } from './channelTalkPayload';

export const channelTalkRenderers = {
  'text-content': () => (
    <>
      <Case label="짧은 텍스트">
        <PanelWidth>
          <TextContent content={textPayload(textContentShort)} />
        </PanelWidth>
      </Case>
      <Case label="긴 텍스트 (여러 줄)">
        <PanelWidth>
          <TextContent content={textPayload(textContentLong)} />
        </PanelWidth>
      </Case>
    </>
  ),
  'block-content': () => (
    <>
      <Case label="text · 마크다운 (굵게/기울임/링크)">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentMarkdown)} />
        </PanelWidth>
      </Case>
      <Case label="text · 평문 (markdown 필드 생략 → text 폴백)">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentPlainText)} />
        </PanelWidth>
      </Case>
      <Case label="code · 짧은 코드 (언어 라벨 bash)">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentCodeShort)} />
        </PanelWidth>
      </Case>
      <Case label="code · 긴 코드 (언어 라벨 typescript)">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentCodeLong)} />
        </PanelWidth>
      </Case>
      <Case label="bullets">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentBullets)} />
        </PanelWidth>
      </Case>
      <Case label="혼합 (text + code + bullets)">
        <PanelWidth>
          <BlockContent content={blockPayload(blockContentMixed)} />
        </PanelWidth>
      </Case>
    </>
  ),
  'button-content': () => (
    <>
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
    </>
  ),
  'form-content': () => (
    <>
      <Case label="다양한 input_type (9개)">
        <PanelWidth>
          <FormContent content={formPayload(formContentVariedInputs)} />
        </PanelWidth>
      </Case>
      <Case label="빈 inputs 배열">
        <PanelWidth>
          <FormContent content={formPayload(formContentEmptyInputs)} />
        </PanelWidth>
      </Case>
    </>
  ),
  'file-content': () => (
    <>
      <Case label="파일 1개">
        <PanelWidth>
          <FileContent
            content={filePayload(fileContentSingle)}
            connector="channel_talk"
            documentId="channel_talk:user_chat:dev-fixture"
          />
        </PanelWidth>
      </Case>
      <Case label="파일 여러 개 (다양한 타입·크기)">
        <PanelWidth>
          <FileContent
            content={filePayload(fileContentMultiple)}
            connector="channel_talk"
            documentId="channel_talk:user_chat:dev-fixture"
          />
        </PanelWidth>
      </Case>
    </>
  ),
  'message-item': () => (
    <>
      {messageItemVariants.map((variant) => (
        <Case key={variant.item.id} label={variant.label}>
          <PanelWidth>
            <MessageItem item={variant.item} connector="channel_talk" documentId="channel_talk:user_chat:dev-fixture" />
          </PanelWidth>
        </Case>
      ))}
    </>
  ),
  'panel-content': () => (
    <>
      <Case label="현실적인 전체 대화 (3개 날짜 그룹, 메시지·콘텐츠 혼합)">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={fullConversationResponse} />
        </PanelFrame>
      </Case>
      <Case label="메시지 0건 (빈 대화)">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={emptyConversationResponse} />
        </PanelFrame>
      </Case>
    </>
  ),
} satisfies Partial<Record<EntrySlug, () => ReactNode>>;
