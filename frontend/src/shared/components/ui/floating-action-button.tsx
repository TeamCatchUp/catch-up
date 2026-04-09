'use client';

import HeadphoneIcon from '@/public/icons/icon/headphone.svg';
import WebTrafficIcon from '@/public/icons/icon/web_traffic.svg';
import { SLACK_CONNECT_URL } from '@/shared/constants/externalLinks';

import { Button } from './button';
import { Tooltip, TooltipContent, TooltipTrigger } from './tooltip';

export default function FloatingActionButton() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="fab-primary"
          size="lg"
          className="fixed right-5 bottom-5 z-70 size-13 transition-transform hover:scale-[1.038]"
          asChild
        >
          <a href={SLACK_CONNECT_URL} target="_blank" rel="noopener noreferrer" aria-label="CatchUp 문의하기">
            <HeadphoneIcon className="size-6.5" />
          </a>
        </Button>
      </TooltipTrigger>
      <TooltipContent side="top" align="end" className="flex max-w-85 flex-col gap-1 px-1.5 py-1.5">
        <div className="flex items-center gap-1.5">
          <WebTrafficIcon className="size-5 shrink-0 text-white" />
          <span className="text-label-xsmall text-white">CatchUp 문의하기</span>
        </div>
        <p className="text-label-xsmall text-alpha-white-75">에러 / 사용법 등의 문의를 남겨주세요.</p>
      </TooltipContent>
    </Tooltip>
  );
}
