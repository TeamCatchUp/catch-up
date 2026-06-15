'use client';

// "동료에게 묻기 전, Catch Up에게 물어보세요" promo 카드.
// 하단 "질문하기" 버튼 클릭 시 /search (캐치스턴트 AI 채팅 페이지)로 이동.

import { useRouter } from 'next/navigation';

import ChannelTalk from '@/public/icons/logo/ChannelTalk.svg';
import Confluence from '@/public/icons/logo/Confluence.svg';
import GitHub from '@/public/icons/logo/GitHub.svg';
import Jira from '@/public/icons/logo/Jira.svg';
import CatchupLogoWhite from '@/public/icons/logo/logo_catchup_white.svg';
import Slack from '@/public/icons/logo/Slack.svg';
import { Button } from '@/shared/components/ui/button';
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
    <div
      className={cn(
        'bg-fill-normal-strong border-line-normal-normal flex w-full flex-col gap-4 overflow-clip rounded-xl border p-5',
        className,
      )}
    >
      <div className="flex flex-1 flex-col items-start gap-8">
        <div className="flex flex-col items-start gap-2.5">
          <div className="bg-icon-strong text-text-normal-inverse flex size-10.5 items-center justify-center overflow-clip rounded-xl">
            <CatchupLogoWhite className="h-5 w-5.5" />
          </div>
          <span className="text-body-xsmall text-text-normal-alternative">캐치스턴트 AI에게 질문하기</span>
          <h3 className="text-heading-large text-text-normal-normal whitespace-pre-line">
            {`동료에게 묻기 전, \nCatch Up에게 물어보세요.`}
          </h3>
        </div>
        <div className="flex w-full flex-col items-start gap-4">
          <div className="flex items-center">
            {SOURCE_LOGOS.map((Logo, i) => (
              <div
                key={i}
                className={cn(
                  'bg-fill-normal-normal border-line-normal-normal flex size-9 items-center justify-center overflow-clip rounded-full border-[0.5px] p-1',
                  i < SOURCE_LOGOS.length - 1 && '-mr-1',
                )}
              >
                <Logo className={Logo === ChannelTalk ? 'size-5' : 'size-6'} />
              </div>
            ))}
          </div>
          <p className="text-body-small text-text-normal-neutral whitespace-pre-line">
            {`여러 문서에 흩어진 내용을 연결해 원인, 흐름, \n관련 히스토리까지 한 번에 정리해드립니다`}
          </p>
        </div>
      </div>
      <Button
        variant="capsule-outline-mono"
        size="sm"
        type="button"
        onClick={() => router.push('/search')}
        className="text-text-normal-normal w-full"
      >
        질문하기
      </Button>
    </div>
  );
}
