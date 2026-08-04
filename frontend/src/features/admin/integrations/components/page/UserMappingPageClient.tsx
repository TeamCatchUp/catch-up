'use client';

import UserMappingView from '../view/UserMappingView';

/**
 * 관리자 — 이용자 매핑 페이지.
 *
 * 셸 규칙은 커넥터 연결 페이지와 같다(Figma `17060:73886`도 같은 구조):
 * 좌우 padding 64, 상단 36, 제목 블록과 본문 사이 gap 40, 제목·부제 사이 gap 8,
 * `max-w-292`(1168)라 1440에서 콘텐츠가 정확히 1040이 된다.
 *
 * 구 화면(`IntegrationsSection`)에 있던 임베딩 카드·진행 패널은 신규 디자인에
 * 없다 — 임베딩은 커넥터 연결 화면이 담당한다. 두 컴포넌트는 팀원 화면
 * 리디자인(스펙 ③) 때까지 삭제하지 않고 남긴다.
 */
export default function UserMappingPageClient() {
  return (
    <section className="mx-auto flex w-full flex-col gap-10 px-16 pt-9 pb-30 min-[1440px]:max-w-292">
      <div className="flex flex-col gap-2">
        <h1 className="text-heading-xlarge text-text-normal-normal">이용자 매핑</h1>
        <p className="text-body-small text-text-normal-alternative">CatchUp에서 사용하는 앱을 찾아 관리합니다.</p>
      </div>

      <UserMappingView />
    </section>
  );
}
