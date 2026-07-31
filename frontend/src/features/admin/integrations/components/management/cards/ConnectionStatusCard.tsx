import IconCloudCheckFilled from '@/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '@/public/icons/icon/cloud_off.svg';
import IconOpenInNew from '@/public/icons/icon/open_in_new.svg';
import { Button } from '@/shared/components/ui/button';

interface ConnectionStatusCardProps {
  connected: boolean;
  /** 미연동 시 IconCloudOff 표시 여부. 일반 도구 true, 채널톡 false — 현행 렌더 보존용. */
  showDisconnectedIcon: boolean;
  /** OAuth install 진입점. 전달하지 않으면 "연동하기" 버튼을 렌더하지 않는다. */
  onInstall?: () => void;
  /** "원문 보기"를 shared Button으로 렌더할지. 채널톡 true, 일반 false — 현행 렌더 보존용. */
  useSharedSourceButton: boolean;
}

/**
 * "연동 상태 관리" 카드.
 * IntegrationManagementSection과 ChannelTalkManagementPanel에 복제돼 있던 두 벌을 한 벌로 합쳤다.
 * 두 벌 사이의 차이는 통일하지 않고 prop으로 재현한다 — 승인 없이 시각을 바꾸지 않기 위해서다.
 */
export default function ConnectionStatusCard({
  connected,
  showDisconnectedIcon,
  onInstall,
  useSharedSourceButton,
}: ConnectionStatusCardProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="text-heading-small text-text-normal-normal">연동 상태 관리</h3>

      <div className="border-line-normal-assistive bg-fill-normal-strong overflow-hidden rounded-xl border">
        <div className="border-line-normal-neutral flex items-center justify-between gap-8 border-b px-4 py-3">
          <span className="text-body-small text-text-normal-normal">연동 상태</span>
          <div className="flex items-center gap-1">
            {connected ? (
              <div className="flex items-center gap-1 px-1.5 py-1">
                <IconCloudCheckFilled className="text-icon-primary-assistive size-4.5 shrink-0" />
                <span className="text-body-xsmall text-text-primary-assistive">연동됨</span>
              </div>
            ) : (
              <>
                {showDisconnectedIcon ? (
                  <div className="flex items-center gap-1 px-1.5 py-1">
                    <IconCloudOff className="text-text-normal-assistive size-5" />
                    <span className="text-body-xsmall text-text-normal-alternative">연동 안됨</span>
                  </div>
                ) : (
                  <span className="text-body-xsmall text-text-normal-alternative">연동 안됨</span>
                )}
                {onInstall && (
                  <button
                    type="button"
                    onClick={onInstall}
                    className="text-body-xsmall text-text-primary-assistive cursor-pointer rounded-full px-1.5 py-1"
                  >
                    연동하기
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between gap-8 px-4 py-3">
          <span className="text-body-small text-text-normal-normal">보안 관련 설명</span>
          {useSharedSourceButton ? (
            <Button variant="text-secondary-mono" size="sm" className="h-7">
              원문 보기
              <IconOpenInNew className="size-5" />
            </Button>
          ) : (
            <button
              type="button"
              className="text-body-xsmall text-text-normal-neutral flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1"
            >
              원문 보기
              <IconOpenInNew className="text-icon-normal-normal size-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
