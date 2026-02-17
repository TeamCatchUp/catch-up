import { cn } from '@/shared/utils/cn';

import type { IntegrationMenuItem, IntegrationService } from '../../types/integrations';
import JiraGuideSection from './JiraGuideSection';

import IconCloudCheckFilled from '/public/icons/icon/cloud_check_filled.svg';
import IconCloudOff from '/public/icons/icon/cloud_off.svg';
import IconOpenInNew from '/public/icons/icon/open_in_new.svg';
import IconRotate from '/public/icons/icon/rotate.svg';

interface IntegrationManagementSectionProps {
  integrationMenu: IntegrationMenuItem[];
  selectedService: IntegrationService;
  onSelectService: (service: IntegrationService) => void;
  lastSyncedAt: string;
  spaceRows: string[];
}

/** 관리자 협업툴 연동 관리 섹션 */
const IntegrationManagementSection = ({
  integrationMenu,
  selectedService,
  onSelectService,
  lastSyncedAt,
  spaceRows,
}: IntegrationManagementSectionProps) => {
  return (
    <div className="flex gap-8">
      <div className="flex w-81.25 flex-col gap-4">
        {integrationMenu.map(({ service, Icon, actionText, connected }) => {
          const isSelected = selectedService === service;

          return (
            <button
              key={service}
              type="button"
              onClick={() => onSelectService(service)}
              className={cn(
                'flex h-16 w-81.25 cursor-pointer items-center justify-between rounded-xl border p-4 shadow-[0_0_4px_0_#f7fbff]',
                isSelected ? 'border-blue-30 bg-white' : 'border-neutral-3 bg-white',
              )}
            >
              <div className="flex items-center gap-3">
                <Icon className={service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0'} />
                <span className="text-heading-small text-gray-80">{actionText}</span>
              </div>
              <div className="flex items-center gap-1">
                {connected ? (
                  <>
                    <IconCloudCheckFilled className="h-5 w-5 text-blue-50" />
                    <span className="text-body-xsmall text-blue-50">연동됨</span>
                  </>
                ) : (
                  <>
                    <IconCloudOff className="text-gray-30 h-5 w-5" />
                    <span className="text-body-xsmall text-gray-50">연동 안됨</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex w-160.75 flex-none flex-col gap-6">
        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-small text-gray-80">연동 상태 관리</h3>
          <div className="border-neutral-3 bg-neutral-1 overflow-hidden rounded-xl border">
            <div className="border-neutral-3 flex h-13 items-center justify-between border-b px-4 py-3">
              <span className="text-body-small text-gray-70">동기화</span>
              <div className="flex items-center gap-3">
                <div className="text-body-xsmall flex items-center gap-1.5">
                  <span className="text-gray-50">최근 동기화</span>
                  <span className="text-gray-70">{lastSyncedAt}</span>
                </div>
                <button
                  type="button"
                  className="border-neutral-3 text-body-xsmall text-gray-70 flex h-7.5 min-w-7.5 cursor-pointer items-center justify-center gap-1 rounded-lg border bg-white px-2 py-1"
                >
                  <IconRotate className="text-gray-70 h-6 w-6" />
                  동기화
                </button>
              </div>
            </div>
            <div className="border-neutral-3 flex h-13 items-center justify-between border-b px-4 py-3">
              <span className="text-body-small text-gray-70">연동 상태</span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  className="text-body-xsmall text-gray-70 h-7 cursor-pointer rounded-full px-1.5 py-1"
                >
                  재연결
                </button>
                <button
                  type="button"
                  className="text-body-xsmall h-7 cursor-pointer rounded-full px-1.5 py-1 text-red-50"
                >
                  연결 해제
                </button>
              </div>
            </div>
            <div className="border-neutral-3 flex h-13 items-center justify-between border-b px-4 py-3">
              <span className="text-body-small text-gray-70">보안 관련 설명</span>
              <button
                type="button"
                className="text-body-xsmall text-gray-70 flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1"
              >
                원문 보기
                <IconOpenInNew className="h-4.5 w-4.5" />
              </button>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-small text-gray-70">연동된 데이터 범위</h3>
          <div className="border-neutral-3 bg-neutral-1 text-body-small text-gray-70 flex h-10.75 items-center justify-center rounded-xl border px-5">
            2000.00.00 ~ 2000.00.00
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <h3 className="text-heading-small text-gray-70">연동된 Jira Space</h3>
          <div className="border-neutral-3 bg-neutral-1 overflow-hidden rounded-xl border">
            {spaceRows.map((row, index) => (
              <div
                key={`${row}-${index}`}
                className="border-neutral-3 text-body-small text-gray-70 flex h-13 items-center border-b px-4 py-3"
              >
                <span className="truncate">{row}</span>
              </div>
            ))}
          </div>
        </div>

        {selectedService === 'jira' ? (
          <JiraGuideSection />
        ) : (
          <div className="border-neutral-3 bg-neutral-1 text-body-small text-gray-60 rounded-xl border px-5 py-4">
            선택한 연동 서비스의 상세 설정 UI는 다음 단계에서 확장할 예정입니다.
          </div>
        )}
      </div>
    </div>
  );
};

export default IntegrationManagementSection;
