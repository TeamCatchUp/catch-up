import type { ReactNode } from 'react';

export type ServiceNoticeVariant = 'incident' | 'recovery';

export interface ServiceNoticeContent {
  /** 영속화 키. 새 공지 게시 시 ID를 바꿔 dismiss 초기화 */
  id: string;
  variant: ServiceNoticeVariant;
  title: string;
  body: ReactNode;
}

export const SERVICE_NOTICES: Record<ServiceNoticeVariant, ServiceNoticeContent> = {
  incident: {
    id: 'ai-incident-2026-04-27',
    variant: 'incident',
    title: 'AI 답변 생성 기능 장애 안내',
    body: (
      <>
        <p>
          안녕하세요. <span className="text-content-primary">Catch Up</span> 입니다.
        </p>
        <p>
          현재 AI 답변 생성에 문제가 발생했습니다.
          <br />
          검색해도 답변이 오지 않거나, 평소보다 응답이 지연되고 있습니다.
        </p>
        <p>
          즉시 원인 파악과 복구 작업을 진행하고 있습니다.
          <br />
          정상화되는 대로 본 공지에서 다시 안내드리겠습니다.
        </p>
        <p>서비스 이용에 지장을 드려 진심으로 죄송합니다.</p>
      </>
    ),
  },
  recovery: {
    id: 'ai-recovery-2026-04-27',
    variant: 'recovery',
    title: 'AI 답변 생성 기능 정상화 안내',
    body: (
      <>
        <p>
          안녕하세요. <span className="text-content-primary">Catch Up</span> 입니다.
        </p>
        <p>어제 발생한 AI 답변 생성 기능 장애가 복구되었습니다.</p>
        <p>
          팀 전체가 즉시 대응에 착수해
          <br />
          원인을 파악하고 조치를 완료했습니다.
          <br />
          현재는 모든 기능이 정상적으로 작동하고 있습니다.
        </p>
        <p>
          서비스 이용에 불편을 드려 진심으로 죄송합니다.
          <br />
          동일한 문제가 반복되지 않도록
          <br />
          모니터링과 대응 체계를 강화해 나가겠습니다.
        </p>
        <p>기다려주신 모든 분께 깊이 감사드립니다.</p>
      </>
    ),
  },
};

/** 현재 활성 공지. null이면 모달 미노출. */
/**
 * 'incident -> 'recovery' 로 변경 시, 정상화 안내 공지 팝업으로 변경됨
 * null 로 변경 시, 두 상태 모두 미노출
 */
export const ACTIVE_SERVICE_NOTICE: ServiceNoticeVariant | null = null;
