'use client';

import DashboardImage from '@/public/image/catchup-login.jpg';
import CatchUpLogo from '@/public/icons/logo/catchUp.svg';
import Image from 'next/image';
import IconOpen from '@/public/icons/icon/open_in_new.svg';

export default function Login() {
  const handleGoogleLogin = () => {
    window.location.href = `https://0-0-0-0.example.io/`;
  };

  return (
    <div className="flex h-226.5 w-360 items-center justify-center gap-2.5 bg-white p-6">
      <div className="border-neutral-4 flex flex-[1_0_0] items-center gap-5 self-stretch rounded-2xl border p-6">
        <div className="flex flex-[1_0_0] flex-col items-center gap-24 self-stretch px-30 py-28.5">
          <div className="flex min-w-80 flex-[1_0_0] flex-col items-start gap-8">
            <div className="flex flex-col items-start gap-8 self-stretch">
              <div className="flex flex-col items-start gap-5 self-stretch">
                <CatchUpLogo />
                <div className="self-stretch text-[40px] font-semibold text-black">환영합니다!</div>
              </div>
            </div>
            <div className="flex flex-col items-start gap-10 self-stretch">
              <div className="flex flex-col items-start gap-5 self-stretch">
                <div className="text-body-medium text-gray-70">Google 계정으로 빠르고 안전하게 시작하세요.</div>
                <button
                  onClick={handleGoogleLogin}
                  className="flex min-w-10 cursor-pointer items-center justify-center gap-1 self-stretch rounded-xl bg-blue-50 px-4 py-2.5"
                >
                  <div className="text-body-large cursor-pointer text-white">구글 계정으로 계속하기</div>
                </button>
              </div>
              {/* <div>회원가입</div> */}
            </div>
          </div>
          <div>
            <div className="flex items-start gap-5">
              <div className="flex items-center justify-center gap-0.5 px-1.5 py-1">
                <div className="text-body-xsmall truncate text-gray-50 underline">서비스 이용약관</div>
                <IconOpen />
              </div>
              <div className="flex items-center justify-center gap-0.5 px-1.5 py-1">
                <div className="text-body-xsmall truncate text-gray-50 underline">개인정보처리방침</div>
                <IconOpen />
              </div>
            </div>
          </div>
        </div>
        <Image src={DashboardImage} alt="catchup" className="h-174.5 flex-[1_0_0]" />
      </div>
    </div>
  );
}
