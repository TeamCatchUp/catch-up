'use client';

import Image from 'next/image';

import IconOpen from '@/public/icons/icon/open_in_new.svg';
import CatchUpLogo from '@/public/icons/logo/catchUp.svg';
import DashboardImage from '@/public/image/auth/catchup-login.png';
import { Button } from '@/shared/components/ui/button';

export default function Login() {
  const handleOAuthLogin = () => {
    window.location.href = '/api/v1/auth/oauth/login';
  };

  return (
    <div className="bg-fill-normal flex h-226.5 w-360 items-center justify-center p-6">
      <div className="border-edge-normal flex flex-[1_0_0] items-center gap-5 self-stretch overflow-clip rounded-2xl border p-6">
        <div className="flex min-w-80 flex-[1_0_0] flex-col items-center justify-center gap-24 self-stretch overflow-clip px-28 py-30">
          <div className="flex w-full min-w-80 flex-col gap-8">
            <CatchUpLogo className="h-[55px] w-[181px]" />

            <h1 className="text-display-large text-content-strong w-full">환영합니다!</h1>

            <div className="flex w-full min-w-80 flex-col gap-2.5">
              <p className="text-body-medium text-content-alternative">
                소속 조직의 계정으로 안전하게 로그인하세요.
              </p>
              <Button variant="box-solid-primary" size="lg" className="h-[46px] w-full" onClick={handleOAuthLogin}>
                SSO 통합 로그인하기
              </Button>
            </div>
          </div>

          <div className="flex shrink-0 items-start gap-5">
            <a href="#" className="flex shrink-0 items-center gap-0.5 px-1.5 py-1 whitespace-nowrap">
              <span className="text-body-xsmall text-content-alternative underline">서비스 이용약관</span>
              <IconOpen className="text-content-alternative size-4.5 shrink-0" />
            </a>
            <a href="#" className="flex shrink-0 items-center gap-0.5 px-1.5 py-1 whitespace-nowrap">
              <span className="text-body-xsmall text-content-alternative underline">개인정보처리방침</span>
              <IconOpen className="text-content-alternative size-4.5 shrink-0" />
            </a>
          </div>
        </div>

        <Image src={DashboardImage} alt="catchup" className="h-174.5 flex-[1_0_0] rounded-xl object-cover" />
      </div>
    </div>
  );
}
