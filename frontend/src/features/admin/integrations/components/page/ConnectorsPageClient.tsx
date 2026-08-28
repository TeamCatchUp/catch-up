'use client';

import ConnectorConnectView from '../view/ConnectorConnectView';

/**
 * 관리자 — 커넥터 연결 페이지 셸(제목 블록 + 상태 기계 뷰). 스펙 §5-1.
 * 셸 수치의 실측 근거: docs/specs/2026-08-04-cam256-figma-measurements-design.md
 */
export default function ConnectorsPageClient() {
  return (
    <section className="mx-auto flex w-full flex-col gap-10 px-16 pt-9 pb-5 min-[1440px]:max-w-292">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-xlarge text-text-normal-normal">커넥터 연결</h1>
        <p className="text-body-small text-text-normal-alternative">CatchUp에서 사용하는 앱을 찾아 관리합니다.</p>
      </div>

      <ConnectorConnectView />
    </section>
  );
}
