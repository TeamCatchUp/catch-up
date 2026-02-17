import DefaultProfile from '@/public/icons/icon/default_profile.svg';
import EmptyGraphic from '@/public/icons/icon/empty.svg';
import { cn } from '@/shared/utils/cn';

import type { IntegrationAccountInfo, IntegrationAccountMeta } from '../../../types/integrations';

interface ConnectedAccountCardProps {
  account: IntegrationAccountMeta;
  accountInfo: IntegrationAccountInfo;
  variant: 'user' | 'admin';
  onEditClick: () => void;
}

/** 연동 계정 정보를 표시하는 공통 카드 */
const ConnectedAccountCard = ({ account, accountInfo, variant, onEditClick }: ConnectedAccountCardProps) => {
  const { service, name, Icon } = account;
  const isAdmin = variant === 'admin';
  const isConnected =
    accountInfo.userName !== '-' && accountInfo.userId !== '-' && accountInfo.userEmail !== '-' && !!accountInfo.userId;
  const iconClassName = service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

  const details = isConnected ? (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <DefaultProfile className="border-neutral-1 text-gray-30 size-6.25 shrink-0 rounded-full border" />
        <span className="text-heading-small text-gray-70 truncate">{accountInfo.userName}</span>
      </div>
      <div className="bg-neutral-2 text-body-xsmall inline-flex w-fit rounded-md px-1.5 py-0.5 text-gray-50">
        {accountInfo.userId}
      </div>
      <div className="text-body-xsmall h-5 truncate text-gray-50">{accountInfo.userEmail}</div>
    </div>
  ) : (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-[55px] w-full items-center justify-center overflow-hidden">
        <EmptyGraphic className="h-[55px] w-[203px]" />
      </div>
      <p className="text-label-xsmall text-gray-30 h-5 w-full truncate text-center">
        아직 연결된 {name} 계정이 없어요.
      </p>
    </div>
  );

  const buttonText = isConnected ? '수정하기' : '계정 등록하기';

  return (
    <article
      className={cn(
        'border-neutral-3 flex w-58.75 shrink-0 rounded-xl border bg-white',
        isAdmin ? 'min-h-52.25 flex-col gap-4 p-4' : 'min-h-62.25 flex-col gap-3 p-5',
      )}
    >
      {isAdmin ? (
        <>
          <div className="flex items-center gap-2.5">
            <Icon className={iconClassName} />
            <span className="text-heading-medium text-gray-80">{name}</span>
          </div>
          <div className="flex w-full flex-col gap-3">
            {details}
            <button
              type="button"
              onClick={onEditClick}
              className="box-button-outline-gray text-body-small text-gray-70 h-9 w-full cursor-pointer"
            >
              {buttonText}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-col gap-2.5">
            <Icon className={iconClassName} />
            <span className="text-heading-medium text-gray-80">{name}</span>
          </div>
          {details}
          <button
            type="button"
            onClick={onEditClick}
            className="box-button-outline-gray text-body-small text-gray-70 h-9 w-full cursor-pointer"
          >
            {buttonText}
          </button>
        </>
      )}
    </article>
  );
};

export default ConnectedAccountCard;
