import Image from 'next/image';

import IconSlack from '@/public/icons/logo/Slack.svg';

import { SLACK_GUIDE_IMAGES } from '../../constants/integrationsConfig';

/** Slack 연동 가이드 섹션 */
export default function SlackGuideSection() {
  return (
    <div className="border-line-normal-neutral bg-fill-normal-normal flex flex-col gap-10 overflow-clip rounded-xl border p-6">
      {/* 인트로 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">
          결정이 내려진 순간의 대화, 휘발되지 않는 자산으로
        </h4>
        <p className="text-label-small text-text-normal-normal">
          공식 문서에는 없는 진짜 이유와 빠른 결정들은 보통 Slack 스레드 어딘가에 남아있습니다. 하지만 과거의 대화를
          찾으려 스크롤을 올리는 일은 팀 전체의 시간 낭비입니다. Catch Up은 대화 속에 숨은 맥락을 찾아, 누가 알아? 하고
          사람을 부르는 일을 줄여줍니다.
        </p>
      </div>

      {/* 1. 워크스페이스 연결 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">1. 워크스페이스 연결</h4>
        <p className="text-label-small text-text-normal-normal">
          Catch Up 협업 툴 연동 페이지에서 &apos;연동하기&apos; 버튼을 클릭합니다.
        </p>
        <div className="border-line-normal-neutral bg-fill-normal-normal overflow-clip rounded-xl border px-4 py-2.5">
          <Image
            src={SLACK_GUIDE_IMAGES.integrationPage}
            alt="Catch Up 협업 툴 연동 페이지 - Slack 연동"
            quality={100}
            className="h-auto w-full"
          />
        </div>
        <p className="text-label-small text-text-normal-normal">
          Slack 연동 페이지에서 권한을 승인하고 연결할 Workspace를 선택합니다.
        </p>
        <div className="border-line-normal-neutral bg-fill-normal-normal overflow-clip rounded-xl border px-4 py-2.5">
          <Image
            src={SLACK_GUIDE_IMAGES.permissions}
            alt="Slack 권한 승인 및 Workspace 선택 화면"
            quality={100}
            className="h-auto w-full"
          />
        </div>
        <div className="border-line-normal-normal flex items-start gap-4 rounded-xl border px-3 py-2">
          <IconSlack className="size-6 shrink-0" />
          <div className="flex min-w-0 flex-col">
            <span className="text-body-xsmall text-text-normal-normal">Slack account</span>
            <span className="text-label-xsmall text-text-normal-alternative truncate">
              https://id.atlassian.com/manage-profile/profile-and-visibility
            </span>
          </div>
        </div>
      </div>

      {/* 2. Catch Up 봇 초대 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">2. Catch Up 봇 초대</h4>
        <p className="text-label-small text-text-normal-normal">
          데이터 수집을 허용할 채널에 접속하여 <span className="font-semibold">/invite @CatchUp</span> 명령어를 입력해
          봇을 초대해주세요. 정보 보호를 위해 개인 간 다이렉트 메시지(DM) 및 그룹 DM은 철저히 연동 대상에서 제외됩니다.
        </p>
      </div>

      {/* 3. 채널 확인 및 동기화 */}
      <div className="flex flex-col gap-2">
        <h4 className="text-heading-medium text-text-normal-normal">3. 채널 확인 및 동기화</h4>
        <p className="text-label-small text-text-normal-normal">
          Catch Up 화면에서 봇이 정상적으로 초대된 채널을 확인한 뒤 동기화를 시작합니다. <br />긴 스레드의 대화라도 AI가
          핵심만 먼저 정리하여 답을 주고, 필요할 땐 원문 스레드로 바로 넘어가 전체 맥락을 확인할 수 있습니다.
        </p>
      </div>

      {/* 클로징 */}
      <p className="text-label-small text-text-normal-strong">대화는 흘러가도, 팀이 합의한 지식은 남겨둡니다.</p>
    </div>
  );
}
