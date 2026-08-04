'use client';

import UserMappingView from '../view/UserMappingView';

/**
 * 관리자 — 이용자 매핑 페이지 셸. 셸 규칙은 커넥터 연결 페이지와 같다.
 *
 * 구 화면(`IntegrationsSection`)의 임베딩 카드·진행 패널은 신규 디자인에 없다 —
 * 임베딩은 커넥터 연결 화면이 담당한다. 구 컴포넌트들은 삭제됐고, 팀원 화면
 * 리디자인(스펙 ③)에서 필요하면 git 히스토리(3b316de0 이전)에서 되살린다.
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
