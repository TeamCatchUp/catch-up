import { cn } from '@/shared/utils/cn';

import type { IntegrationAccountInfo, IntegrationAccountMeta } from '../../types/integrations.types';

interface ConnectedAccountCardProps {
  account: IntegrationAccountMeta;
  accountInfo: IntegrationAccountInfo;
  variant: 'user' | 'admin';
}

/** 연동 계정 정보를 표시하는 공통 카드 */
const ConnectedAccountCard = ({ account, accountInfo, variant }: ConnectedAccountCardProps) => {
  const { service, name, Icon } = account;
  const isAdmin = variant === 'admin';
  const iconClassName = service === 'confluence' ? 'h-5.75 w-6 shrink-0' : 'h-6 w-6 shrink-0';

  const details = (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="bg-neutral-2 h-6.25 w-6.25 rounded-full" />
        <span className="text-heading-small text-gray-70">{accountInfo.userName}</span>
      </div>
      <div className="bg-neutral-2 text-body-xsmall text-gray-50 inline-flex w-fit rounded-md px-1.5 py-0.5">{accountInfo.userId}</div>
      <div className="text-body-xsmall text-gray-50 h-5 truncate">{accountInfo.userEmail}</div>
    </div>
  );

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
            <button type="button" className="box-button-outline-gray text-body-small text-gray-70 h-9 w-full cursor-pointer">
              수정하기
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
          <button type="button" className="box-button-outline-gray text-body-small text-gray-70 h-9 w-full cursor-pointer">
            수정하기
          </button>
        </>
      )}
    </article>
  );
};

export default ConnectedAccountCard;
