'use client';

import ConnectorConnectView from '../view/ConnectorConnectView';

/**
 * 관리자 — 커넥터 연결 페이지. 스펙 §5-1의 화면 상태 기계를 렌더한다.
 *
 * Figma 셸(`17122:112580`·`17125:115105`·`17169:74057` 공통):
 * 좌우 padding 64, 상단 36, 제목 블록과 본문 사이 gap 40, 제목·부제 사이 gap 8.
 * 콘텐츠는 1440 뷰포트에서 1040 — SNB 240을 뺀 1200에서 좌우 64를 뺀 값이다.
 * `max-w-292`(1168)가 padding 128을 포함한 섹션 상한이라 콘텐츠가 정확히 1040이 된다.
 *
 * 제목은 "커넥터 연결"이다. 리디자인 전 "협업툴 연동"에서 바뀌었고,
 * 부제가 새로 붙었다(세 프레임 모두 동일).
 */
export default function ConnectorsPageClient() {
  return (
    <section className="mx-auto flex w-full flex-col gap-10 px-16 pt-9 pb-30 min-[1440px]:max-w-292">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-xlarge text-text-normal-normal">커넥터 연결</h1>
        <p className="text-body-small text-text-normal-alternative">CatchUp에서 사용하는 앱을 찾아 관리합니다.</p>
      </div>

      <ConnectorConnectView />
    </section>
  );
}
