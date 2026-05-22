'use client';

// dev preview 갤러리 — 원문 패널 컴포넌트 × 케이스 매트릭스.
// 사용자 피드백 surface: 각 컴포넌트를 백엔드 DTO가 만들 수 있는 모든 상태로 렌더한다.
// 백엔드 불필요 — __fixtures__ 의 목 데이터로만 동작.

import type { ReactNode } from 'react';

import {
  blockContentBulletsNested,
  blockContentBulletsSingle,
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
import OriginalPanelHeader from '@/features/hybrid-search/components/original/OriginalPanelHeader';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/OriginalPanelSkeleton';
import type {
  OriginalBlockPayload,
  OriginalButtonPayload,
  OriginalContent,
  OriginalFilePayload,
  OriginalFormPayload,
  OriginalTextPayload,
} from '@/features/hybrid-search/types/originalApi';

// 리프 콘텐츠 컴포넌트는 discriminated union 이 아닌 구체 payload 타입을 받는다.
// fixture 는 OriginalContent 유니온으로 타입돼 있어, content_type 별로 좁혀 payload 를 꺼낸다.
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

// 갤러리의 라벨 붙은 블록 — 컴포넌트별 섹션 단위.
interface SectionProps {
  title: string;
  description?: string;
  children: ReactNode;
}

function Section({ title, description, children }: SectionProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-heading-medium text-content-normal font-semibold">{title}</h2>
        {description && <p className="text-body-small text-content-alternative">{description}</p>}
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

// 한 케이스 — 라벨 + 그 케이스의 렌더 결과.
interface CaseProps {
  label: string;
  children: ReactNode;
}

function Case({ label, children }: CaseProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-body-xsmall text-content-assistive font-medium">{label}</span>
      {children}
    </div>
  );
}

// 콘텐츠/메시지 컴포넌트를 실제 패널 폭(~360px)에 가깝게 감싸는 컨테이너.
function PanelWidth({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-strong border-edge-neutral w-90 rounded-xl border p-3">{children}</div>
  );
}

// 전체 패널(헤더+스크롤 영역) 컴포넌트를 패널 폭·고정 높이로 감싸는 컨테이너.
function PanelFrame({ children }: { children: ReactNode }) {
  return (
    <div className="bg-fill-strong border-edge-neutral h-160 w-90 overflow-hidden rounded-xl border">
      {children}
    </div>
  );
}

export default function OriginalPanelGalleryPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-12 px-8 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-heading-large text-content-normal font-bold">
          원문 패널 — 컴포넌트 갤러리
        </h1>
        <p className="text-body-medium text-content-alternative">
          ChannelTalk user_chat 원문 패널의 모든 컴포넌트를 상태·케이스별로 렌더합니다. dev 전용
          라우트이며 프로덕션 빌드에서는 노출되지 않습니다.
        </p>
      </header>

      {/* --- 콘텐츠 타입 --- */}

      <Section
        title="TextContent"
        description="payload.text 를 줄바꿈 보존 평문으로 렌더."
      >
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
      </Section>

      <Section
        title="BlockContent"
        description="blocks[] 를 block_type 별로 분기 — text→마크다운, code→코드블럭, bullets→리스트."
      >
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
        <Case label="bullets · 단일 레벨">
          <PanelWidth>
            <BlockContent content={blockPayload(blockContentBulletsSingle)} />
          </PanelWidth>
        </Case>
        <Case label="bullets · 중첩 (들여쓰기)">
          <PanelWidth>
            <BlockContent content={blockPayload(blockContentBulletsNested)} />
          </PanelWidth>
        </Case>
        <Case label="혼합 (text + code + bullets)">
          <PanelWidth>
            <BlockContent content={blockPayload(blockContentMixed)} />
          </PanelWidth>
        </Case>
      </Section>

      <Section
        title="ButtonContent"
        description="buttons[] 를 공통 Button 으로 렌더 — url 있는 버튼만 새 탭 링크."
      >
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
      </Section>

      <Section
        title="FormContent"
        description="form.inputs[] 라벨/값 행. 입력이 많으면 Collapsible 로 접힘."
      >
        <Case label="다양한 input_type · 접힌 상태 (9개 → 임계치 초과)">
          <PanelWidth>
            <FormContent content={formPayload(formContentVariedInputs)} />
          </PanelWidth>
        </Case>
        <Case label="빈 inputs 배열">
          <PanelWidth>
            <FormContent content={formPayload(formContentEmptyInputs)} />
          </PanelWidth>
        </Case>
      </Section>

      <Section title="FileContent" description="files[] 각 요소를 FileRow 로 — 안전 다운로드 링크.">
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
      </Section>

      {/* --- 메시지 --- */}

      <Section
        title="MessageItem"
        description="visibility + author.type 별 변형. 배경 채움은 internal 일 때만."
      >
        {messageItemVariants.map((variant) => (
          <Case key={variant.item.id} label={variant.label}>
            <PanelWidth>
              <MessageItem item={variant.item} />
            </PanelWidth>
          </Case>
        ))}
      </Section>

      {/* --- 날짜 구분선 --- */}

      <Section title="DateIndicator" description="채팅 타임라인의 날짜 구분선.">
        <Case label="날짜 구분선">
          <PanelWidth>
            <DateIndicator date="2026-05-20T09:30:00+09:00" />
          </PanelWidth>
        </Case>
      </Section>

      {/* --- Collapsible primitive --- */}

      <Section
        title="Collapsible"
        description="controlled 접기/펴기 primitive — CustomerInfo/FormContent 가 사용."
      >
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
      </Section>

      {/* --- 상담 정보 --- */}

      <Section
        title="ConsultationInfo"
        description="metadata 의 담당자/태그/설명. detail 부재·태그 없음 케이스 포함."
      >
        {metadataVariants.map((variant) => (
          <Case key={variant.metadata.user_chat_id} label={variant.label}>
            <PanelWidth>
              <ConsultationInfo metadata={variant.metadata} />
            </PanelWidth>
          </Case>
        ))}
      </Section>

      {/* --- 고객 정보 --- */}

      <Section
        title="CustomerInfo"
        description="metadata.customer 의 접기/펴기 섹션. 전체/일부 필드 케이스."
      >
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
      </Section>

      {/* --- 패널 헤더 --- */}

      <Section title="OriginalPanelHeader" description="대화 제목 + 안전한 '원문 열기' 외부 링크.">
        <Case label="제목 + 안전한 url">
          <PanelWidth>
            <OriginalPanelHeader
              title={fullConversationResponse.title}
              url={fullConversationResponse.url}
            />
          </PanelWidth>
        </Case>
        <Case label="url 없음 (링크 미표시)">
          <PanelWidth>
            <OriginalPanelHeader title="원문 열기 링크가 없는 대화" url={null} />
          </PanelWidth>
        </Case>
        <Case label="빈 제목 ('제목 없음' 폴백)">
          <PanelWidth>
            <OriginalPanelHeader title="" url={null} />
          </PanelWidth>
        </Case>
      </Section>

      {/* --- 패널 상태 컴포넌트 --- */}

      <Section
        title="패널 상태 컴포넌트"
        description="OriginalPanel 이 분기하는 형제 상태 — 직접 렌더."
      >
        <Case label="Skeleton (로딩)">
          <PanelFrame>
            <OriginalPanelSkeleton />
          </PanelFrame>
        </Case>
        <Case label="Empty (결과 0건)">
          <PanelFrame>
            <OriginalPanelEmpty />
          </PanelFrame>
        </Case>
        <Case label="Error · 400 (지원하지 않는 원문 유형)">
          <PanelFrame>
            <OriginalPanelError message="지원하지 않는 원문 유형입니다" onRetry={() => {}} />
          </PanelFrame>
        </Case>
        <Case label="Error · 404 (연동 정보 없음)">
          <PanelFrame>
            <OriginalPanelError
              message="원문을 불러올 수 없어요 (연동 정보 없음)"
              onRetry={() => {}}
            />
          </PanelFrame>
        </Case>
        <Case label="Error · 422 (제공처 오류)">
          <PanelFrame>
            <OriginalPanelError message="원문 제공처에서 오류가 발생했어요" onRetry={() => {}} />
          </PanelFrame>
        </Case>
        <Case label="ComingSoon · Jira">
          <PanelFrame>
            <OriginalPanelComingSoon toolName="Jira" />
          </PanelFrame>
        </Case>
        <Case label="ComingSoon · Github">
          <PanelFrame>
            <OriginalPanelComingSoon toolName="Github" />
          </PanelFrame>
        </Case>
        <Case label="ComingSoon · Slack">
          <PanelFrame>
            <OriginalPanelComingSoon toolName="Slack" />
          </PanelFrame>
        </Case>
        <Case label="ComingSoon · 컨플루언스 위키 문서">
          <PanelFrame>
            <OriginalPanelComingSoon toolName="컨플루언스 위키 문서" />
          </PanelFrame>
        </Case>
        <Case label="ComingSoon · 채널톡 도큐먼트">
          <PanelFrame>
            <OriginalPanelComingSoon toolName="채널톡 도큐먼트" />
          </PanelFrame>
        </Case>
      </Section>

      {/* --- OriginalPanelContent 통합 --- */}

      <Section
        title="OriginalPanelContent"
        description="헤더 → 상담정보 → 고객정보 → 날짜 그룹별 메시지의 전체 조립."
      >
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
      </Section>

      {/* --- OriginalPanel 컨테이너 --- */}

      <Section
        title="OriginalPanel (컨테이너)"
        description="connector/entityType/documentId 로 분기. ComingSoon·Empty 는 fetch 없이 렌더, 나머지 상태는 위 '패널 상태 컴포넌트' 섹션 참고."
      >
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
      </Section>
    </div>
  );
}
