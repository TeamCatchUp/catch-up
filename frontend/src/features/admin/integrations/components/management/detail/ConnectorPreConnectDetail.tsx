'use client';

import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';

import { CONNECTOR_CONTENT } from '../../../constants/connectorContent';
import type { IntegrationService } from '../../../types/integrationModel';
import ConfluenceGuideSection from '../guides/ConfluenceGuideSection';
import ConnectorGuideAccordion from '../guides/ConnectorGuideAccordion';
import GithubGuideSection from '../guides/GithubGuideSection';
import JiraGuideSection from '../guides/JiraGuideSection';
import SlackGuideSection from '../guides/SlackGuideSection';
import ConnectorDetailHeader from './ConnectorDetailHeader';
import ConnectorSampleQuestions from './ConnectorSampleQuestions';
import ConnectorScopeCompare from './ConnectorScopeCompare';
import ConnectorScopeTable from './ConnectorScopeTable';
import MappingCheckPopover from './MappingCheckPopover';

// 채널톡은 가이드 섹션이 없다 — 현행에도 없음
const GUIDES: Partial<Record<IntegrationService, React.ReactNode>> = {
  slack: <SlackGuideSection />,
  jira: <JiraGuideSection />,
  confluence: <ConfluenceGuideSection />,
  github: <GithubGuideSection />,
};

interface ConnectorPreConnectDetailProps {
  service: IntegrationService;
  /** 매핑 확인하기 → /admin/user-mapping 이동 */
  onCheckMapping: () => void;
  /** 연결하기 — OAuth 이탈. 채널톡은 2스텝 진입 */
  onConnect: () => void;
}

/**
 * (D) 커넥터 상세 — 연동 전. 스펙 §5-2, Figma `16922:134087`.
 * 헤더 + 매핑 팝오버(닫기 전까지 표시) + 소개 + 예시 질문 + 연동 범위 +
 * 대조 카드 + 가이드 아코디언.
 *
 * 버튼 라벨은 `연결하기`다(Figma `16922:134092` 실측). 매핑 확인 모달은
 * 구현하지 않는다(스펙 결정 #1) — 팝오버가 비차단 안내를 대신한다.
 */
export default function ConnectorPreConnectDetail({
  service,
  onCheckMapping,
  onConnect,
}: ConnectorPreConnectDetailProps) {
  const content = CONNECTOR_CONTENT[service];
  const [popoverOpen, setPopoverOpen] = useState(true);
  const guide = GUIDES[service];

  return (
    <div className="flex flex-col gap-8">
      <div className="relative">
        <ConnectorDetailHeader
          service={service}
          title={content.name}
          description={content.headerDescription}
          actions={
            <>
              <Button variant="box-soft-primary" size="md" onClick={onCheckMapping}>
                매핑 확인하기
              </Button>
              <Button variant="box-solid-primary" size="md" onClick={onConnect}>
                연결하기
              </Button>
            </>
          }
        />
        {/*
         * Figma `16922:134092`의 Tooltip은 ABSOLUTE다 — 흐름에 넣으면 아래 본문을
         * 밀어낸다. 실측: 헤더 아래 20(y83 - 헤더 63), 우측 안쪽 123(1040-557-360).
         * 123은 [매핑 확인하기]를 가리키도록 [연결하기] 폭만큼 비켜 둔 값이라
         * 스케일에 없다. left-0은 좁은 pane에서 max-w가 잡히도록 반대편을 연다.
         */}
        {popoverOpen && (
          <div className="absolute top-full right-0 left-0 z-10 mt-5 flex justify-end pr-[123px] max-md:pr-0">
            <MappingCheckPopover onClose={() => setPopoverOpen(false)} />
          </div>
        )}
      </div>

      <p className="text-body-small text-text-normal-neutral">{content.intro}</p>

      <ConnectorSampleQuestions service={service} />
      <ConnectorScopeTable service={service} />
      <ConnectorScopeCompare service={service} />

      {guide && <ConnectorGuideAccordion service={service}>{guide}</ConnectorGuideAccordion>}
    </div>
  );
}
