'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Profile from '@/public/icons/icon/profile.svg';
import { authMutations } from '@/shared/queries/auth.mutations';
import { authQueries } from '@/shared/queries/auth.queries';
import { useUserStore } from '@/shared/store/userStore';
import { cn } from '@/shared/utils/cn';

const JOB_LEVEL_LABEL: Record<string, string> = {
  executive: '경영진',
  leader: '팀장',
  member: '팀원',
};

/**
 * 마이페이지 프로필 화면을 렌더링
 */
const ProfilePage = () => {
  const { user } = useUserStore();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === 'admin';

  const { data: profile } = useQuery(authQueries.profile());

  const logoutMutation = useMutation({
    ...authMutations.logout(),
    onSuccess: () => {
      queryClient.clear();
      window.location.href = '/login';
    },
  });

  const basicInfoRows = [
    { label: '이름', value: profile?.name ?? user?.name ?? '' },
    { label: '메일 / 사번', value: profile?.email ?? user?.email ?? '' },
    { label: '직급', value: JOB_LEVEL_LABEL[profile?.job_level ?? ''] ?? '' },
  ];

  return (
    <section className="flex flex-col gap-6 px-16 pt-9 pb-30">
      <h1 className="text-heading-xlarge text-content-normal">계정</h1>
      <div className="border-edge-neutral h-px w-full border-b" />

      <div className="flex flex-col gap-8">
        <div className="flex items-end gap-4">
          {profile?.picture ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src={profile.picture} alt={profile.name} className="h-27.5 w-27.5 rounded-2xl object-cover" />
          ) : (
            <Profile className="h-27.5 w-27.5 rounded-2xl" />
          )}
          <div className="flex flex-col gap-1">
            <span className="text-heading-xlarge text-content-normal">{profile?.name ?? user?.name ?? ''}</span>
            <div className="text-content-alternative flex gap-1">
              <span className="text-body-small">{profile?.department ?? ''}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <div className="bg-fill-strong rounded-md px-5 py-1.5">
            <span className="text-heading-small text-content-neutral">기본 정보</span>
          </div>
          <div className="text-body-small flex flex-col px-4">
            {basicInfoRows.map((row, index) => (
              <div
                key={row.label}
                className={cn(
                  'flex items-center gap-8 py-3',
                  index !== basicInfoRows.length - 1 && 'border-edge-neutral border-b',
                )}
              >
                <span className="text-icon-normal w-20">{row.label}</span>
                <span className="text-content-normal">{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <div className="bg-fill-strong rounded-md px-5 py-1.5">
            <span className="text-heading-small text-content-neutral">계정 관리</span>
          </div>
          <div className="text-body-small flex flex-col px-4">
            <div className="border-edge-neutral flex items-center justify-between gap-5 border-b py-3">
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <span className="text-heading-small text-content-normal">로그아웃 하기</span>
                <span className="text-label-small text-content-alternative">현재 계정에서 로그아웃됩니다.</span>
              </div>
              <button
                type="button"
                onClick={() => logoutMutation.mutate()}
                disabled={logoutMutation.isPending}
                className="capsule-button-outline-mono text-body-small text-content-normal disabled:text-content-assistive h-9 cursor-pointer px-3 py-1.5 disabled:cursor-not-allowed"
              >
                로그아웃
              </button>
            </div>
            <div className="flex items-center justify-between gap-5 py-3">
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <span className="text-heading-small text-content-normal">계정 삭제하기</span>
                <span className="text-label-small text-content-alternative">
                  모든 데이터가 영구 삭제되며 복구할 수 없습니다.
                </span>
              </div>
              <button
                type="button"
                disabled={isAdmin}
                aria-disabled={isAdmin}
                className={cn(
                  'text-body-small h-9 rounded-full border px-3 py-1.5',
                  isAdmin
                    ? 'border-edge-neutral bg-fill-strong text-content-assistive cursor-not-allowed'
                    : 'hover:bg-red-5 active:bg-red-10 bg-fill-normal cursor-pointer border-red-50 text-red-50',
                )}
              >
                삭제
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ProfilePage;
