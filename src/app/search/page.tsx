'use client';

import { useState } from 'react';
import Image from 'next/image';

import arrow from '@/public/icons/icon/arrow_send.svg';
import add from '@/public/icons/icon/add_small.svg';

import jira from '@/public/icons/logo/Jira.svg';
import wiki from '@/public/icons/logo/Wiki.svg';
import github from '@/public/icons/logo/GitHub.svg';
import slack from '@/public/icons/logo/Slack.svg';

import divder from '@/public/icons/icon/divider.svg';

import person from '@/public/icons/icon/person.svg';
import tag from '@/public/icons/icon/tag.svg';
import space from '@/public/icons/icon/space.svg';
import arrowRight from '@/public/icons/icon/arrow_right2.svg';

export default function Search() {
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const hasText = inputValue.trim().length > 0;

  return (
    <div className="flex flex-col items-center gap-4 self-stretch pt-16 pb-16">
      <div className="flex h-24 flex-col items-center justify-center gap-3">
        <div className="text-display-xlarge text-nomal-normal">반갑습니다, 이진수님!</div>
        <div className="text-heading-large text-nomal-alternative">
          무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
        </div>
      </div>
      <div className="text-blue-55 text-body-small flex items-center gap-2.5">
        {['연차 신청 방법', '권한 신청 방법', '피그마 관련 내부 그라운드 룰', '데이터 요청 방법'].map((text) => (
          <div
            key={text}
            className="rounded-rounded border-blue-30 bg-blue-1 flex h-9 items-center justify-center gap-1.5 border border-solid px-3 py-1.5"
          >
            {text}
          </div>
        ))}
      </div>
      <div
        className={`shadow-rag-bar border-neutral-4 flex w-[760px] flex-col items-center gap-2.5 rounded-[28px] border border-solid bg-white ${isFocused ? 'h-[502px] max-h-[540px] min-h-[370px] p-3 px-4' : 'h-auto p-3 px-4'} `}
      >
        <div className="flex w-full items-center justify-between">
          <div className="flex flex-1 items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center p-1.5">
              <Image src={add} alt="Add" />
            </div>
            <input
              className="text-body-medium w-full outline-none"
              placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
            />
          </div>
          <div
            className={`rounded-rounded flex items-center border border-solid p-2 ${hasText ? 'border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'}`}
          >
            <Image src={arrow} alt="Send" className={`${hasText ? 'brightness-0 invert' : ''}`} />
          </div>
        </div>

        {isFocused && (
          <div className="border-neutral-4 flex w-full flex-col gap-2.5 overflow-y-auto border-t pt-4">
            <div className="flex items-center gap-1.5 self-stretch px-1.5">
              <div className="flex items-center gap-2">
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={jira} alt="jira" />
                  <div className="text-gray-80 text-body-small">Jira</div>
                </div>
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={wiki} alt="wiki" />
                  <div className="text-gray-80 text-body-small">Wiki</div>
                </div>
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={github} alt="github" />
                  <div className="text-gray-80 text-body-small">github</div>
                </div>
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={slack} alt="slack" />
                  <div className="text-gray-80 text-body-small">Slack</div>
                </div>
              </div>
              <Image src={divder} alt="divder" />
              <div className="flex items-center gap-2">
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={person} alt="person" />
                  <div className="text-gray-80 text-body-small">담당자</div>
                </div>
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={tag} alt="tag" />
                  <div className="text-gray-80 text-body-small">부서명</div>
                </div>
                <div className="border-neutral-3 flex h-9 max-w-36 items-center justify-center gap-1 rounded-lg border border-solid bg-white px-2 py-1.5">
                  <Image src={space} alt="space" />
                  <div className="text-gray-80 text-body-small">프로젝트</div>
                </div>
              </div>
              <div className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
                <Image src={arrowRight} alt="right" />
              </div>
            </div>
            <div className="flex flex-[1_0_0] flex-col items-start gap-4 self-stretch">
              <div className="flex flex-col items-start gap-2.5 self-stretch">
                <div className="flex items-center justify-center gap-2.5 px-1.5">
                  <div className="text-nomal-alternative text-body-small">최근 질문</div>
                </div>
              </div>
              <div className="flex flex-col items-start gap-2.5 self-stretch">
                <div className="flex items-center justify-center gap-2.5 px-1.5">
                  <div className="text-nomal-alternative text-body-small">최근 확인한 지라 티켓</div>
                </div>
              </div>
              <div className="flex flex-col items-start gap-2.5 self-stretch">
                <div className="flex items-center justify-center gap-2.5 px-1.5">
                  <div className="text-nomal-alternative text-body-small">캐치업에서 열어본 파일</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
