'use client';

import Image from 'next/image';
import { useRouter } from 'next/navigation';

import IconOpen from '@/public/icons/icon/open_in_new.svg';
import CatchUpLogo from '@/public/icons/logo/catchUp.svg';
import DashboardImage from '@/public/image/catchup-login.jpg';
import { Button } from '@/shared/components/ui/button';

export default function Login() {
  const router = useRouter();

  const handleGoogleLogin = () => {
    window.location.href = `https://0-0-0-0.example.io/`;
  };

  const handleSignup = () => {
    router.push('/onboarding');
  };

  return (
    <div className="flex h-226.5 w-360 items-center justify-center bg-white p-6">
      <div className="flex flex-[1_0_0] items-center gap-5 self-stretch overflow-clip rounded-2xl border border-neutral-4 p-6">
        <div className="flex min-w-80 flex-[1_0_0] flex-col items-center justify-center gap-24 self-stretch overflow-clip px-28 py-30">
          <div className="flex w-full min-w-80 flex-col gap-8">
            <CatchUpLogo className="w-[181px] h-[55px]" />

            <h1 className="w-full text-display-large tracking-tight text-gray-90">
              환영합니다!
            </h1>

            <div className="flex w-full min-w-80 flex-col gap-2.5">
              <p className="text-body-medium tracking-tight text-gray-60">
                Google 계정으로 빠르고 안전하게 시작하세요.
              </p>
              <Button
                variant="box-solid-primary"
                size="lg"
                className="h-[46px] w-full"
                onClick={handleGoogleLogin}
              >
                구글 계정으로 계속하기
              </Button>
            </div>

            <div className="flex w-full min-w-80 flex-col gap-2.5">
              <p className="text-body-medium tracking-tight text-gray-60">
                Catch Up이 처음이신가요?
              </p>
              <Button
                variant="box-outline-gray"
                size="lg"
                className="h-[46px] w-full"
                onClick={handleSignup}
              >
                회원가입 시작하기
              </Button>
            </div>
          </div>

          <div className="flex items-start gap-5">
            <div className="flex items-center justify-center gap-0.5 px-1.5 py-1">
              <div className="text-body-xsmall truncate text-gray-50 underline">서비스 이용약관</div>
              <IconOpen className="size-4.5" />
            </div>
            <div className="flex items-center justify-center gap-0.5 px-1.5 py-1">
              <div className="text-body-xsmall truncate text-gray-50 underline">개인정보처리방침</div>
              <IconOpen className="size-4.5" />
            </div>
          </div>
        </div>

        <Image src={DashboardImage} alt="catchup" className="h-174.5 flex-[1_0_0] object-cover" />
      </div>
    </div>
  );
}
