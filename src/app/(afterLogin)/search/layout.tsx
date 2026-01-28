import TopNavbar from '@/components/common/topNavbar/TopNavbar';
import IconCancel from '@/public/icons/icon/cancel.svg';
import IconLightbulb from '@/public/icons/icon/lightbulb.svg';
import Jira from '@/public/image/catchstantJira1.jpg';
import Git from '@/public/image/catchstantGit1.jpg';
import Image from 'next/image';

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-home-gradient flex flex-[1_0_0] flex-col items-start self-stretch">
      <TopNavbar pageType="home" />
      <div className="felx h-screen flex-col items-start self-stretch">
        {children}
        <div className="flex flex-col items-center gap-4 self-stretch px-52 pt-10 pb-30">
          <div className="flex w-190 flex-col items-center gap-3">
            <div className="flex items-center justify-between self-stretch">
              <div className="flex items-center gap-2">
                <IconLightbulb className="text-blue-30" />
                <div className="text-heading-small text-gray-50">캐치스턴트 AI에서 정확한 답변을 얻으려면</div>
              </div>
              <div className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
                <IconCancel />
              </div>
            </div>
            <div className="flex items-start gap-6 self-stretch">
              <Image src={Jira} alt="jira" className="w-[368px]" />
              <Image src={Git} alt="git" className="w-[368px]" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
