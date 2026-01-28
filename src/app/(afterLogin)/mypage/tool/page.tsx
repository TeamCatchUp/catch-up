import IconJira from '@/public/icons/logo/Jira28.svg';
import IconAT from '@/public/icons/logo/atlassian.svg';
import IconRotate from '@/public/icons/icon/rotate.svg';
import IconCheck from '@/public/icons/icon/check.svg';
import ImgAPItoken from '@/public/image/apitoken.jpg';
import ImgAPItoken1 from '@/public/image/apitoken1.jpg';

import Image from 'next/image';
export default function ToolPage() {
  return (
    <div className="flex items-start gap-6 self-stretch px-16 pt-6">
      <div className="flex flex-col items-start gap-3">
        <div className="border-blue-30 bg-whit flex w-[325px] items-center gap-5 rounded-xl border-2 p-4">
          <div className="border-0.5 border-neutral-5 flex h-10.5 w-10.5 shrink-0 flex-col justify-center gap-2.5 rounded-xl px-4 py-[5px]">
            <IconJira />
          </div>
          <div className="flex flex-[1_0_0] flex-col items-start gap-1">
            <div className="text-heading-large text-gray-70">Jira</div>
            <div className="text-body-xsmall text-gray-50">팀이 진행한 모든 업무가 한 곳에 정리됩니다.</div>
          </div>
        </div>
      </div>
      <div className="flex flex-[1_0_0] flex-col items-start gap-9">
        <div className="flex flex-col items-end gap-2.5 self-stretch">
          <div className="flex items-center justify-between self-stretch">
            <div className="flex items-center justify-center gap-2.5 px-1.5 py-1">
              <div className="text-heading-medium text-gray-80">API Key</div>
            </div>
            <div className="flex items-center gap-2.5">
              <button className="text-gray-70 text-body-small box-button-outline-gray flex h-9 min-w-9 items-center justify-center gap-1.5 px-2.5 py-1.5">
                <IconRotate className="h-5 w-5" />
                <div>동기화하기</div>
              </button>
              <button
                className="text-body-small box-button-solid-primary flex h-9 min-w-9 items-center justify-center gap-1.5 px-2.5 py-1.5 text-white"
                disabled
              >
                <IconCheck className="h-5 w-5" />
                <div>연동됨</div>
              </button>
            </div>
          </div>
          <div className="border-neutral-3 flex flex-col items-start gap-2.5 self-stretch rounded-xl border px-5 py-4">
            <div className="flex flex-col items-start gap-4 self-stretch">
              <div className="flex h-7 items-center gap-12 self-stretch">
                <div className="text-body-small text-gray-70 flex items-start gap-2">API Key</div>
                <div className="bg-alpha-black-10 h-5 flex-[1_0_0] rounded-md"></div>
                <button className="box-button-outline-gray px-1.5 py-1">수정</button>
              </div>
              <div className="flex items-center justify-between self-stretch">
                <div className="text-body-small text-gray-70 flex items-start gap-2">보안 관련 설명</div>
                <button className="box-button-outline-gray px-1.5 py-1">원문보기</button>
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-start justify-center gap-1.5 self-stretch">
          <div className="flex items-center gap-2.5 px-1.5 py-1">
            <div className="text-gray-80 text-heading-medium">Jira (Atlassian) API 토큰 발급 가이드</div>
          </div>
          <div className="border-neutral-4 flex flex-col items-start gap-10 self-stretch rounded-xl border px-6 py-5">
            <div className="text-body-small text-gray-70">
              Jira와의 연동을 위해 Atlassian 계정에서 API 토큰을 발급받아야 합니다. 아래 절차를 따라 키를 생성하고
              입력해 주세요.
            </div>
            <div className="flex flex-col items-start gap-2.5 self-stretch">
              <div className="flex flex-col items-start gap-1.5">
                <div className="text-gray-80 text-heading-medium">1. 계정 보안 페이지 접속</div>
                <div className="text-gray-70 text-body-small">
                  먼저 Atlassian 계정 관리 페이지에 접속하여 로그인합니다.
                </div>
              </div>
              <div className="border-neutral-4 flex flex-col items-start gap-2.5 rounded-xl border px-3 py-2">
                <div className="flex items-center gap-4">
                  <IconAT />
                  <div className="flex w-[334px] flex-col items-start">
                    <div className="text-gray-80 text-body-xsmall">Atlassian account</div>
                    <div className="text-body-xsmall text-gray-50">
                      https://id.atlassian.com/manage-profile/profile-and-visibility
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-2.5 self-stretch">
              <div className="flex flex-col items-start gap-2 self-stretch">
                <div className="text-gray-80 text-heading-medium">2. 보안 설정 이동 및 토큰 생성</div>
                <Image src={ImgAPItoken1} alt="apitoken" />
                <div className="text-body-small text-gray-70">
                  1) 상단 메뉴 또는 페이지 내에서 '보안(Security)' 탭을 클릭합니다.
                  <br />
                  2) 'API 토큰 만들기 및 관리(Create and manage API tokens)' 항목을 찾아 클릭합니다. <br />
                  3) 페이지 상단의 [API 토큰 만들기] 버튼을 누릅니다.
                </div>
                <Image src={ImgAPItoken} alt="apitoken" />
              </div>
            </div>
            <div className="flex flex-col items-start gap-2.5 self-stretch">
              <div className="text-gray-80 text-heading-medium">3. 토큰 정보 입력 (ID 및 만료일)</div>
              <div className="text-body-small text-gray-70">
                토큰을 식별할 수 있는 이름(Label)과 유효 기간을 설정합니다.
              </div>
              <div className="flex flex-col items-start gap-0.5 self-stretch">
                <div className="text-body-small text-gray-70">
                  · 레이블(ID) 입력: 이 토큰이 어디에 쓰이는지 알 수 있도록 명확한 이름(예: 서비스명_연동키)을
                  입력합니다.
                </div>
                <div className="text-body-small text-gray-70">· 만료 날짜 설정: 토큰의 유효 기간을 설정합니다.</div>
              </div>
              <div className="bg-neutral-1 flex flex-col items-start gap-2.5 rounded-xl px-3 py-2">
                <div className="flex flex-col items-start gap-1.5 self-stretch">
                  <div className="text-body-xsmall text-gray-80">💡 권장 설정</div>
                  <div className="text-heading-small text-gray-70">
                    토큰의 유효 기간은 최대 1년입니다. 서비스 이용 중 인증 만료로 인한 연결 끊김을 방지하기 위해, 가능한
                    가장 긴 기간(1년)으로 설정하는 것을 강력히 권장합니다.
                  </div>
                </div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-2.5 self-stretch">
              <div className="text-gray-80 text-heading-medium">4. API 키 복사 및 저장</div>
              <div className="text-body-small text-gray-70">토큰 생성이 완료되면 화면에 API 키가 표시됩니다.</div>
              <div className="flex flex-col items-start gap-0.5 self-stretch">
                <div className="text-body-small text-gray-70">
                  1) [클립보드에 복사] 아이콘을 클릭하여 키를 복사합니다. <br />
                  2) 복사한 키를 우리 서비스의 입력창에 즉시 붙여넣기(Ctrl+V) 해주세요.
                </div>
              </div>
              <div className="bg-neutral-1 flex flex-col items-start gap-2.5 rounded-xl px-3 py-2">
                <div className="flex flex-col items-start gap-1.5 self-stretch">
                  <div className="text-body-xsmall text-gray-80">⚠️ 주의사항 : 반드시 바로 복사하세요!</div>
                  <div className="text-heading-small text-gray-70">
                    보안상의 이유로 발급된 API 키는 창을 닫으면 다시 조회할 수 없습니다. 만약 복사하지 못하고 창을
                    닫았다면, 기존 키를 삭제하고 처음부터 다시 생성해야 합니다.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
