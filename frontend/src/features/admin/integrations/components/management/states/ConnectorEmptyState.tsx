import { Button } from '@/shared/components/ui/button';

import { CONNECTOR_LOGOS } from '../../../constants/connectorLogos';
import type { IntegrationService } from '../../../types/integrationModel';

/**
 * 일러스트 로고 칩의 배치.
 * Figma `17122:112585`의 절대 좌표를 장식 박스(474×474) 기준으로 옮긴 값이다.
 * 4개는 바깥 원(r=237), GitHub만 안쪽 원(r=175) 위에 있다.
 */
const LOGO_POSITIONS: readonly { service: IntegrationService; left: number; top: number }[] = [
  { service: 'jira', left: 102, top: 6 },
  { service: 'slack', left: 16, top: 82 },
  { service: 'github', left: 214, top: 41 },
  { service: 'channel_talk', left: 307, top: -6 },
  { service: 'confluence', left: 419, top: 95 },
];

/** 위→아래로 사라지는 원 테두리. Figma가 gradient stroke로 그린 것을 mask로 재현한다 */
const FADE_55 = '[mask-image:linear-gradient(180deg,#000_0%,transparent_55%)]';
const FADE_42 = '[mask-image:linear-gradient(180deg,#000_0%,transparent_42%)]';

interface ConnectorEmptyStateProps {
  onStart: () => void;
}

/**
 * 연결된 커넥터가 하나도 없을 때의 안내.
 * Figma `17122:112578` — 카드 padding 200/32, gap 24. 장식은 absolute라 흐름에서 빠진다.
 */
export default function ConnectorEmptyState({ onStart }: ConnectorEmptyStateProps) {
  return (
    <div className="border-line-normal-neutral relative flex flex-1 flex-col items-center gap-6 overflow-hidden rounded-2xl border px-8 py-50">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-11.75 left-1/2 size-118.5 -translate-x-1/2"
      >
        <div
          className={`border-line-normal-assistive bg-fill-normal-normal shadow-card absolute inset-0 rounded-full border ${FADE_55}`}
        />
        <div
          className={`border-line-normal-assistive bg-fill-normal-normal shadow-card absolute inset-15.5 rounded-full border ${FADE_42}`}
        />
        {LOGO_POSITIONS.map(({ service, left, top }) => {
          const Logo = CONNECTOR_LOGOS[service];
          return (
            <div
              key={service}
              style={{ left, top }}
              className="border-line-normal-neutral bg-fill-normal-normal shadow-rag-bar absolute flex size-11.5 items-center justify-center rounded-xl border"
            >
              <Logo className="size-8" />
            </div>
          );
        })}
      </div>

      <h2 className="text-heading-large text-text-normal-normal relative">아직 연결된 협업툴이 없어요</h2>
      <p className="text-body-small text-text-normal-alternative relative text-center whitespace-pre-line">
        {'Slack · Jira · Confluence 같은 협업툴을 연결하면,\n팀에 흩어진 대화와 문서를 한데 모아 필요한 답을 근거와 함께 찾아드려요.'}
      </p>
      {/* Figma 원문은 "커텍터 연결하기"(오타). 사용자 확인 후 교정했다 */}
      <Button variant="box-solid-primary" size="lg" onClick={onStart} className="relative">
        커넥터 연결하기
      </Button>
    </div>
  );
}
