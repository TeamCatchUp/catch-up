import DefaultProfile from '@/public/icons/icon/default_profile.svg';

import type { UserOption } from './UserSelectSection';

interface SelectedUserProfileProps {
  user: UserOption;
}

/** 선택된 이용자 프로필 카드 */
const SelectedUserProfile = ({ user }: SelectedUserProfileProps) => {
  return (
    <div className="flex items-start gap-4">
      <DefaultProfile className="border-neutral-2 text-gray-30 size-14 shrink-0 rounded-full border-4 border-white" />
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
        <h2 className="text-heading-large text-gray-70">{user.name}</h2>
        <p className="text-body-small text-gray-50 tracking-tight">
          {user.department} · {user.rank}
        </p>
      </div>
    </div>
  );
};

export default SelectedUserProfile;
