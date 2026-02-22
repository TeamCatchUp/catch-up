import Image from 'next/image';

import { ATLASSIAN_PROFILE_URL, JIRA_GUIDE_IMAGES } from '../../constants/integrations';

import IconAT from '/public/icons/logo/atlassian.svg';

/** Jira (Atlassian) & Confluence 연동 가이드 섹션 */
const JiraGuideSection = () => {
  return (
    <div className="border-neutral-3 flex flex-col gap-10 overflow-clip rounded-xl border bg-white p-6">
      {/* 인트로 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-gray-80">기획과 태스크의 흐름, 질문 대신 검색으로 해결하세요.</h4>
        <p className="text-label-small text-gray-80">
          기획 문서는 Confluence에, 구체적인 업무 할당은 Jira에 남아있습니다. &quot;그때 왜 이 스펙으로
          결정했더라?&quot; 누군가에게 묻는 순간, 질문하는 사람도 답하는 사람도 일이 멈춥니다. Catch Up은 흩어진 문서를
          한데 모아, 필요한 답을 근거와 함께 바로 보여줍니다.
        </p>
      </div>

      {/* 1. Atlassian 사이트 연결 및 권한 승인 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-gray-80">1. Atlassian 사이트 연결 및 권한 승인</h4>
        <p className="text-label-small text-gray-80">
          Catch Up 협업 툴 연동 페이지에서 &apos;계정 등록하기&apos; 버튼을 클릭합니다.
        </p>
        <div className="border-neutral-3 overflow-clip rounded-xl border bg-white px-4 py-2.5">
          <Image
            src={JIRA_GUIDE_IMAGES.integrationPage}
            alt="Catch Up 협업 툴 연동 페이지 - 계정 등록하기 버튼"
            quality={100}
            className="h-auto w-full"
          />
        </div>
        <p className="text-label-small text-gray-80">
          Catch Up과 연결할 팀의 Site(예:{' '}
          <a href="http://company.atlassian.net/" target="_blank" rel="noopener noreferrer" className="underline">
            company.atlassian.net
          </a>
          )를 선택하고 권한을 승인해주세요.
        </p>
        <button
          type="button"
          onClick={() => window.open(ATLASSIAN_PROFILE_URL, '_blank')}
          className="border-neutral-4 flex cursor-pointer items-start gap-4 rounded-xl border px-3 py-2 text-left"
        >
          <div className="flex size-10 shrink-0 items-center justify-center bg-white">
            <IconAT className="size-10" />
          </div>
          <div className="flex min-w-0 flex-col">
            <span className="text-body-xsmall text-gray-80">Atlassian account</span>
            <span className="text-label-xsmall truncate text-gray-50">{ATLASSIAN_PROFILE_URL}</span>
          </div>
        </button>
      </div>

      {/* 2. 대상 Project / Space 지정 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-gray-80">2.대상 Project / Space 지정</h4>
        <div className="border-neutral-3 overflow-clip rounded-xl border bg-white px-4 py-2.5">
          <Image
            src={JIRA_GUIDE_IMAGES.projectSpace}
            alt="Jira Project / Space 지정 화면"
            quality={100}
            className="h-auto w-full"
          />
        </div>
        <p className="text-label-small text-gray-80">
          연동 담당자가 열람할 수 있는 목록이 표시됩니다. 전체 데이터가 아닌, 동기화가 필요한 특정 Project와 Space만
          지정할 수 있습니다. 허락하지 않은 공간은 들여다보지 않습니다.
        </p>
      </div>

      {/* 3. 문서의 지식화 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-gray-80">3. 문서의 지식화</h4>
        <p className="text-label-small text-gray-80">
          수집된 자산은 AI 요약 및 임베딩 과정을 거치며, 이후 검색 시 &apos;왜 이 문서가 답변의 근거로
          선택되었는지&apos; 핵심 발췌와 함께 제공됩니다.
        </p>
      </div>

      {/* 클로징 */}
      <p className="text-label-small text-black">팀이 커져도, 기획의 맥락은 그대로 남습니다.</p>
    </div>
  );
};

export default JiraGuideSection;
