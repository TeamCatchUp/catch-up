'use client';

// "동료에게 묻기 전, Catch Up에게 물어보세요" promo 카드.
// 클릭 시 /search (캐치스턴트 AI 채팅 페이지)로 이동.

import { useRouter } from 'next/navigation';

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import CatchupLogoWhite from '@/public/icons/logo/logo_catchup_white.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import { cn } from '@/shared/utils/cn';

interface CatchupPromoCardProps {
  className?: string;
}

const SOURCE_LOGOS: ReadonlyArray<React.FC<React.SVGProps<SVGSVGElement>>> = [
  Slack,
  Confluence,
  GitHub,
  Jira,
  ChannelTalk,
];

export default function CatchupPromoCard({ className }: CatchupPromoCardProps) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => router.push('/search')}
      className={cn(
        'bg-fill-strong border-edge-normal flex w-full cursor-pointer flex-col gap-4 overflow-clip rounded-xl border pt-5 text-left transition-colors',
        className,
      )}
    >
      <div className="flex flex-col gap-2.5 px-5">
        <div className="bg-icon-strong text-content-inverse flex h-10.5 w-10.5 items-center justify-center rounded-xl">
          <CatchupLogoWhite className="h-5 w-5.5" />
        </div>
        <span className="text-body-xsmall text-content-alternative">캐치스턴트 AI에게 질문하기</span>
        <h3 className="text-heading-large text-content-normal whitespace-pre-line">
          {`동료에게 묻기 전, \nCatch Up에게 물어보세요.`}
        </h3>
        <p className="text-body-small text-content-neutral whitespace-pre-line">
          {`여러 문서에 흩어진 내용을 연결해 원인, 흐름, \n관련 히스토리까지 한 번에 정리해드립니다`}
        </p>
      </div>
      <div className="bg-fill-normal flex w-full flex-col gap-2 p-5">
        <div className="flex items-center">
          {SOURCE_LOGOS.map((Logo, i) => (
            <div
              key={i}
              className="bg-fill-strong border-edge-normal -mr-1 flex h-6 w-6 items-center justify-center overflow-clip rounded-full border"
            >
              <Logo className="h-4 w-4" />
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-2">
          <div className="bg-fill-strong h-[15px] w-67 rounded-md" />
          <div className="bg-fill-strong h-[15px] w-52 rounded-md" />
          <div className="bg-fill-strong h-[15px] w-37 rounded-md" />
        </div>
      </div>
    </button>
  );
}
