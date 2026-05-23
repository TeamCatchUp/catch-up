'use client';

// slug 별 케이스 렌더러. fixture/feature 컴포넌트 import 가 모두 이 파일로 격리된다.
// 'use client' — Collapsible/Error 케이스가 inline 핸들러(onOpenChange/onRetry)를 넘기므로
// RSC 직렬화 경계를 건너뛰어야 함. ENTRY_RENDERERS 는 이 모듈 내부에서만 쓰고,
// 외부로는 <EntryRenderer slug={...} /> Component 만 노출 (server 가 string slug 만 전달).

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
import Collapsible from '@/features/hybrid-search/components/original/Collapsible';
import ConsultationInfo from '@/features/hybrid-search/components/original/ConsultationInfo';
import BlockContent from '@/features/hybrid-search/components/original/contents/BlockContent';
import ButtonContent from '@/features/hybrid-search/components/original/contents/ButtonContent';
import FileContent from '@/features/hybrid-search/components/original/contents/FileContent';
import FormContent from '@/features/hybrid-search/components/original/contents/FormContent';
import TextContent from '@/features/hybrid-search/components/original/contents/TextContent';
import CustomerInfo from '@/features/hybrid-search/components/original/CustomerInfo';
import DateIndicator from '@/features/hybrid-search/components/original/DateIndicator';
import MessageItem from '@/features/hybrid-search/components/original/MessageItem';
import OriginalPanel from '@/features/hybrid-search/components/original/OriginalPanel';
import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/OriginalPanelComingSoon';
import OriginalPanelContent from '@/features/hybrid-search/components/original/OriginalPanelContent';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/OriginalPanelSkeleton';
import type {
  OriginalBlockPayload,
  OriginalButtonPayload,
  OriginalContent,
  OriginalFilePayload,
  OriginalFormPayload,
  OriginalTextPayload,
} from '@/features/hybrid-search/types/originalApi';

import Case from '../_components/Case';
import PanelFrame from '../_components/PanelFrame';
import PanelWidth from '../_components/PanelWidth';
import type { EntrySlug } from './entries';

// payload narrowing — fixtures 는 OriginalContent 유니온이라 컴포넌트가 받는 구체 payload 로 좁힌다.
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

const ENTRY_RENDERERS: Record<EntrySlug, () => ReactNode> = {
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
          <FileContent content={filePayload(fileContentSingle)} />
        </PanelWidth>
      </Case>
      <Case label="파일 여러 개 (다양한 타입·크기)">
        <PanelWidth>
          <FileContent content={filePayload(fileContentMultiple)} />
        </PanelWidth>
      </Case>
    </>
  ),
  'message-item': () => (
    <>
      {messageItemVariants.map((variant) => (
        <Case key={variant.item.id} label={variant.label}>
          <PanelWidth>
            <MessageItem item={variant.item} />
          </PanelWidth>
        </Case>
      ))}
    </>
  ),
  'date-indicator': () => (
    <Case label="날짜 구분선">
      <PanelWidth>
        <DateIndicator date="2026-05-20T09:30:00+09:00" />
      </PanelWidth>
    </Case>
  ),
  'consultation-info': () => (
    <>
      {metadataVariants.map((variant) => (
        <Case key={variant.metadata.user_chat_id} label={variant.label}>
          <PanelWidth>
            <ConsultationInfo metadata={variant.metadata} />
          </PanelWidth>
        </Case>
      ))}
    </>
  ),
  'customer-info': () => (
    <>
      <Case label="전체 필드">
        <PanelWidth>
          <CustomerInfo customer={customerFull} />
        </PanelWidth>
      </Case>
      <Case label="일부 필드 ('없음' placeholder)">
        <PanelWidth>
          <CustomerInfo customer={customerPartial} />
        </PanelWidth>
      </Case>
      <Case label="customer 자체가 undefined">
        <PanelWidth>
          <CustomerInfo customer={undefined} />
        </PanelWidth>
      </Case>
    </>
  ),
  collapsible: () => (
    <Case label="기본 (CustomerInfo·FormContent 케이스 참고)">
      <PanelWidth>
        <Collapsible
          open
          onOpenChange={() => {}}
          header={
            <span className="text-body-small text-content-normal py-2 font-medium">
              펼쳐진 헤더
            </span>
          }
        >
          <p className="text-body-small text-content-alternative pb-2">접히는 본문 영역입니다.</p>
        </Collapsible>
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
          <OriginalPanelError
            message="원문을 불러올 수 없어요 (연동 정보 없음)"
            onRetry={() => {}}
          />
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
  'panel-content': () => (
    <>
      <Case label="현실적인 전체 대화 (3개 날짜 그룹, 메시지·콘텐츠 혼합)">
        <PanelFrame>
          <OriginalPanelContent data={fullConversationResponse} />
        </PanelFrame>
      </Case>
      <Case label="메시지 0건 (빈 대화)">
        <PanelFrame>
          <OriginalPanelContent data={emptyConversationResponse} />
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
};

interface EntryRendererProps {
  slug: EntrySlug;
}

export default function EntryRenderer({ slug }: EntryRendererProps) {
  const renderer = ENTRY_RENDERERS[slug];
  return renderer ? renderer() : null;
}
