'use client';

import { useState } from 'react';
import TopNavbar from '@/components/shared/topNavbar/TopNavbar';
import IconLightbulb from '@/public/icons/icon/lightbulb.svg';
import Jira from '@/public/image/AIJIRA1.png';
import Git from '@/public/image/aiGit.png';
import Image from 'next/image';
import { GithubGuideCard, JiraGuideCard } from '@/components/UI/AIGuideUI';

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  const [activeCard, setActiveCard] = useState<'jira' | 'git' | null>(null);

  const toggleCard = (type: 'jira' | 'git') => {
    setActiveCard(activeCard === type ? null : type);
  };

  return (
    <div className="bg-home-gradient flex flex-[1_0_0] flex-col items-start self-stretch">
      <TopNavbar pageType="home" />
      <div className="felx min-h-screen flex-col items-start self-stretch">
        {children}
        <div className="flex flex-col items-center gap-4 self-stretch px-52 pt-10 pb-30">
          <div className="flex w-190 flex-col items-center gap-3">
            <div className="flex items-center justify-between self-stretch">
              <div className="flex items-center gap-2">
                <IconLightbulb className="text-blue-30" />
                <div className="text-heading-small text-gray-50">캐치스턴트 AI에서 정확한 답변을 얻으려면</div>
              </div>
            </div>

            <div className="flex items-start gap-6 self-stretch">
              <button onClick={() => toggleCard('jira')} className={`transition-transform hover:scale-[1.02]`}>
                <Image src={Jira} alt="jira" className="w-[368px] cursor-pointer" />
              </button>

              <button onClick={() => toggleCard('git')} className={`transition-transform hover:scale-[1.02]`}>
                <Image src={Git} alt="git" className="w-[368px] cursor-pointer" />
              </button>
            </div>
          </div>
          {activeCard === 'jira' && <JiraGuideCard onClose={() => setActiveCard(null)} />}
          {activeCard === 'git' && <GithubGuideCard onClose={() => setActiveCard(null)} />}
        </div>
      </div>
    </div>
  );
}
