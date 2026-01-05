'use client';

import DashboardImage from '@/public/image/splash screen.svg';
import CatchUpLogo from '@/public/icons/logo/catchUp.svg';

export default function Login() {
  const handleGoogleLogin = () => {
    window.location.href = `https://0-0-0-0.example.io`;
  };

  return (
    <div className="flex h-[906px] w-[1440px] items-center justify-between bg-white p-10">
      <DashboardImage />
      <div className="flex flex-[1_0_0] items-center gap-2.5 self-stretch px-[120px] py-[114px]">
        <div className="flex flex-[1_0_0] flex-col items-start gap-24">
          <div className="flex flex-col items-start gap-8 self-stretch">
            <div className="flex flex-col items-start gap-5 self-stretch">
              <CatchUpLogo />
              <div className="self-stretch text-[40px] font-semibold text-black">
                사람은 떠나도, <br />
                지식은 남아야 하니까.
              </div>
            </div>
          </div>
          <div className="flex flex-col items-start gap-10 self-stretch">
            <div className="flex flex-col items-start gap-5 self-stretch">
              <div className="text-body-medium text-gray-70">Google 계정으로 빠르고 안전하게 시작하세요.</div>
              <div className="flex min-w-10 items-center justify-center gap-1 self-stretch rounded-xl bg-blue-50 px-4 py-2.5">
                <button onClick={handleGoogleLogin} className="text-body-large text-white">
                  구글 계정으로 계속하기
                </button>
              </div>
            </div>
            <div>회원가입</div>
          </div>
        </div>
      </div>
    </div>
  );
}
