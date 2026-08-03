'use client';

import ConnectorConnectView from '../view/ConnectorConnectView';

/** 관리자 — 커넥터 연결 페이지. 스펙 §5-1의 화면 상태 기계를 렌더한다. */
export default function ConnectorsPageClient() {
  return (
    <section className="mx-auto flex w-full flex-col gap-6 px-16 pt-9 pb-30 min-[1440px]:max-w-287">
      <h1 className="text-heading-xlarge text-text-normal-normal">협업툴 연동</h1>
      <ConnectorConnectView />
    </section>
  );
}
