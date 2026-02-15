import Image from 'next/image';

import { ATLASSIAN_PROFILE_URL, JIRA_GUIDE_IMAGES } from '../../constants/integrations.constants';

import IconAT from '/public/icons/logo/atlassian.svg';

/** Jira(Atlassian) 연동 가이드 섹션 */
const JiraGuideSection = () => {
  return (
    <div className="flex flex-col gap-2.5">
      <h3 className="text-heading-small text-gray-80">Jira (Atlassian) 연동 가이드</h3>
      <div className="border-neutral-3 flex flex-col gap-10 rounded-xl border bg-white px-6 py-5">
        <p className="text-body-small text-gray-70">
          Jira와의 연동을 위해 Atlassian 계정에서 API 토큰을 발급받아야 합니다. 아래 절차를 따라 키를 생성하고 입력해
          주세요.
        </p>

        <div className="flex flex-col gap-2.5">
          <div className="flex flex-col gap-1.5">
            <h4 className="text-heading-medium text-gray-80">1. 계정 보안 페이지 접속</h4>
            <p className="text-body-small text-gray-70">먼저 Atlassian 계정 관리 페이지에 접속하여 로그인합니다.</p>
          </div>
          <button
            type="button"
            onClick={() => window.open(ATLASSIAN_PROFILE_URL, '_blank')}
            className="border-neutral-4 flex cursor-pointer items-start gap-4 rounded-xl border px-3 py-2 text-left"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center bg-white">
              <IconAT className="h-10 w-10" />
            </div>
            <div className="flex min-w-0 flex-col">
              <span className="text-body-xsmall text-gray-80">Atlassian account</span>
              <span className="text-label-xsmall truncate text-gray-50">{ATLASSIAN_PROFILE_URL}</span>
            </div>
          </button>
        </div>

        <div className="flex flex-col gap-2.5">
          <div className="flex flex-col gap-2">
            <h4 className="text-heading-medium text-gray-80">2. 보안 설정 이동 및 토큰 생성</h4>
            <div className="border-neutral-4 overflow-hidden rounded-xl border bg-white px-4 py-2">
              <Image
                src={JIRA_GUIDE_IMAGES.tokenSetting}
                alt="Atlassian API 토큰 설정 화면"
                quality={100}
                className="h-auto w-full"
              />
            </div>
            <p className="text-body-small text-gray-70">
              1) 상단 메뉴 또는 페이지 내에서 &apos;보안(Security)&apos; 탭을 클릭합니다.
              <br />
              2) &apos;API 토큰 만들기 및 관리(Create and manage API tokens)&apos; 항목을 찾아 클릭합니다.
              <br />
              3) 페이지 상단의 [API 토큰 만들기] 버튼을 누릅니다.
            </p>
            <div className="border-neutral-4 relative flex w-115.25 flex-col items-start gap-2.5 overflow-hidden rounded-xl border bg-white px-4 py-2.5">
              <Image
                src={JIRA_GUIDE_IMAGES.token}
                alt="Atlassian API 토큰 생성 예시"
                quality={100}
                className="h-33.5 w-107.25 object-cover"
              />
              <div className="top-5.9 pointer-events-none absolute left-45.5 h-6 w-17.25 border-3 border-red-50" />
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2.5">
          <h4 className="text-heading-medium text-gray-80">3. 토큰 정보 입력 (ID 및 만료일)</h4>
          <p className="text-body-small text-gray-70">토큰을 식별할 수 있는 이름(Label)과 유효 기간을 설정합니다.</p>
          <div className="text-body-small text-gray-70 flex flex-col gap-0.5">
            <p>• 레이블(ID) 입력: 서비스 용도를 알 수 있도록 명확한 이름을 입력합니다.</p>
            <p>• 만료 날짜 설정: 토큰의 유효 기간을 설정합니다.</p>
          </div>
          <div className="bg-neutral-1 flex flex-col gap-1.5 rounded-xl px-3 py-2">
            <span className="text-body-xsmall text-gray-80">권장 설정</span>
            <p className="text-heading-small text-gray-70">
              토큰의 유효 기간은 최대 1년입니다. 가능한 가장 긴 기간으로 설정해 만료로 인한 연결 끊김을 예방하세요.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-2.5">
          <h4 className="text-heading-medium text-gray-80">4. API 키 복사 및 저장</h4>
          <p className="text-body-small text-gray-70">토큰 생성이 완료되면 화면에 API 키가 표시됩니다.</p>
          <div className="text-body-small text-gray-70 flex flex-col gap-0.5">
            <p>1) [클립보드에 복사] 아이콘을 클릭해 키를 복사합니다.</p>
            <p>2) 복사한 키를 서비스 입력창에 즉시 붙여넣기(Ctrl+V) 해주세요.</p>
          </div>
          <div className="bg-neutral-1 flex flex-col gap-1.5 rounded-xl px-3 py-2">
            <span className="text-body-xsmall text-gray-80">주의사항 : 반드시 바로 복사하세요!</span>
            <p className="text-heading-small text-gray-70">
              보안상의 이유로 발급된 API 키는 창을 닫으면 다시 조회할 수 없습니다. 복사하지 못했다면 키를 재생성해야
              합니다.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default JiraGuideSection;
