import Image from 'next/image';

import { GITHUB_GUIDE_IMAGES } from '../../constants/integrationsConfig';

/** GitHub 연동 가이드 섹션 */
export default function GithubGuideSection() {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-10 overflow-clip rounded-xl border p-6">
      {/* 인트로 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">코드가 담고 있는 맥락, 이제 한 번에 찾아요.</h4>
        <p className="text-label-small text-text-normal-normal">
          개발자의 코드는 확실한 결과물이지만, &apos;왜 이렇게 짰는지&apos;에 대한 맥락은 파편화되어 있습니다. PR을
          뒤지고, 커밋 기록을 따라가다 보면 흐름이 끊기고 시간만 새게 되죠. Catch Up은 흩어진 코드의 맥락을 연결해, 팀이
          다시 일의 흐름을 이어갈 수 있게 돕습니다.
        </p>
      </div>

      {/* 1. GitHub 앱 설치 및 권한 승인 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">1. GitHub 앱 설치 및 권한 승인</h4>
        <p className="text-label-small text-text-normal-normal">
          Catch Up 협업 툴 연동 페이지에서 &apos;연동하기&apos; 버튼을 클릭합니다.
        </p>
        <div className="border-line-normal-neutral bg-fill-normal-normal overflow-clip rounded-xl border px-4 py-2.5">
          <Image
            src={GITHUB_GUIDE_IMAGES.integrationPage}
            alt="Catch Up 협업 툴 연동 페이지 - GitHub 연동하기 버튼"
            quality={100}
            className="h-auto w-full"
          />
        </div>
        <p className="text-label-small text-text-normal-normal">
          이후 GitHub 연동 페이지로 이동하여 팀이 함께 볼 Organization을 선택하고 접근 권한을 승인해주세요.
        </p>
        <div className="border-line-normal-neutral bg-fill-normal-normal overflow-clip rounded-xl border px-4 py-2.5">
          <Image
            src={GITHUB_GUIDE_IMAGES.install}
            alt="GitHub CatchUp Connector 설치 화면"
            quality={100}
            className="h-auto w-full"
          />
        </div>
      </div>

      {/* 2. 동기화할 Repository 선택 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">2. 동기화할 Repository 선택</h4>
        <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-2.5 overflow-clip rounded-xl border px-4 py-2.5">
          <Image
            src={GITHUB_GUIDE_IMAGES.repository}
            alt="GitHub Repository 선택 화면"
            quality={100}
            className="h-auto w-full"
          />
          <Image
            src={GITHUB_GUIDE_IMAGES.repositoryInstall}
            alt="GitHub Repository Install 버튼"
            quality={100}
            className="h-auto w-[58%]"
          />
        </div>
        <p className="text-label-small text-text-normal-normal">
          권한이 확인된 Repository 목록 중, 팀의 지식으로 활용할 곳만 최종 선택합니다. <br />
          명시적으로 선택하지 않은 공간의 데이터는 절대 접근하지 않습니다.
        </p>
      </div>

      {/* 3. Github 데이터의 지식화 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">3. Github 데이터의 지식화</h4>
        <p className="text-label-small text-text-normal-normal">
          동기화된 텍스트는 Catch Up의 AI가 요약하고 임베딩하여, 질문에 맞는 핵심 답과 코드 원문(딥링크)을 함께 제공할
          준비를 마칩니다. 이후의 모든 업데이트는 실시간으로 반영됩니다.
        </p>
      </div>

      {/* 클로징 */}
      <p className="text-label-small text-text-normal-strong">찾느라 쓰던 시간, 이제 개발에 집중하세요</p>
    </div>
  );
}
