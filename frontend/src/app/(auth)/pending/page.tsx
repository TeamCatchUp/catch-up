'use client';

import Image from 'next/image';

import ErrorIcon from '@/public/icons/icon/error_blue.svg';
import IconOpen from '@/public/icons/icon/open_in_new.svg';
import CatchUpLogo from '@/public/icons/logo/catchUp.svg';
import DashboardImage from '@/public/image/catchup-login.jpg';
import { Button } from '@/shared/components/ui/button';
import { useCurrentUser } from '@/shared/hooks/useCurrentUser';

export default function PendingPage() {
  const { isLoading, isFetching, refetch } = useCurrentUser(true);

  const handleRequestApproval = () => {
    window.location.href = 'mailto:?subject=CatchUp%20승인%20요청';
  };

  if (isLoading) {
    return (
      <div className="flex size-full items-center justify-center">
        <p className="text-heading-large text-content-alternative">로딩 중...</p>
      </div>
    );
  }

  return (
    <div className="flex h-226.5 w-360 items-center justify-center bg-fill-normal p-6">
      <div className="border-edge-normal flex flex-[1_0_0] items-center gap-5 self-stretch overflow-clip rounded-2xl border p-6">
        <div className="flex min-w-80 flex-[1_0_0] flex-col items-center justify-center gap-24 self-stretch overflow-clip px-28 py-30">
          <div className="flex w-full min-w-80 flex-col gap-8">
            <CatchUpLogo className="h-[55px] w-[181px]" />

            <div className="flex items-start gap-3">
              <div className="border-edge-assistive bg-blue-1 shrink-0 rounded-full border p-2">
                <ErrorIcon className="size-5.5" />
              </div>
              <h1 className="text-display-large text-content-strong tracking-tight whitespace-nowrap">
                관리자의 승인을 기다리고 있어요
              </h1>
            </div>

            <div className="flex min-w-80 flex-col gap-2.5">
              <p className="text-body-medium text-content-alternative tracking-tight">승인이 완료되면 바로 알려드릴게요.</p>
              <Button variant="box-solid-primary" size="lg" className="h-[46px] w-full" onClick={handleRequestApproval}>
                관리자에게 승인 요청하기
              </Button>
              <Button
                variant="box-outline-gray"
                size="lg"
                className="h-[46px] w-full"
                onClick={() => refetch()}
                disabled={isFetching}
              >
                내 상태 다시 확인하기
              </Button>
            </div>
          </div>

          <div className="flex shrink-0 items-start gap-5">
            <a href="#" className="flex shrink-0 items-center gap-0.5 px-1.5 py-1 whitespace-nowrap">
              <span className="text-body-xsmall text-content-alternative underline">서비스 이용약관</span>
              <IconOpen className="size-6 shrink-0 text-content-alternative" />
            </a>
            <a href="#" className="flex shrink-0 items-center gap-0.5 px-1.5 py-1 whitespace-nowrap">
              <span className="text-body-xsmall text-content-alternative underline">개인정보처리방침</span>
              <IconOpen className="size-6 shrink-0 text-content-alternative" />
            </a>
          </div>
        </div>

        <Image src={DashboardImage} alt="CatchUp 대시보드" className="h-174.5 flex-[1_0_0] object-cover" />
      </div>
    </div>
  );
}
