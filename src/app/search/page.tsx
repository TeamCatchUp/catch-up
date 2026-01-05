'use client';

import { useState } from 'react';
import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconWiki from '@/public/icons/logo/Wiki.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconSlack from '@/public/icons/logo/Slack.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconArrowRight from '@/public/icons/icon/arrow_right2.svg';

import { FilterChip } from '@/components/UI/SearchFilter';
import { SearchOptionButton } from '@/components/UI/SearchOptionButton';
import { SearchSuggestion } from '@/components/UI/SearchSuggestion';
import { sendChatQuery } from 'src/util/sendChatQuery';

export default function Search() {
  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!inputValue.trim()) return;

    setLoading(true);
    try {
      const result = await sendChatQuery(inputValue);
      console.log('서버 응답:', result);
      setInputValue(''); // 전송 후 입력창 초기화
    } catch (error) {
      alert('전송에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  };

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
          <FilterChip key={text} label={text} />
        ))}
      </div>
      <div
        className={`shadow-rag-bar border-neutral-4 flex w-[760px] flex-col items-center gap-2.5 border border-solid bg-white ${isFocused ? 'h-[502px] max-h-[540px] min-h-[370px] rounded-[28px] p-3 px-4' : 'rounded-rounded h-auto p-3 px-4'} `}
      >
        <div className="flex w-full items-center justify-between">
          <div className="flex flex-1 items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center p-1.5">
              <IconAdd className="h-6 w-6" />
            </div>
            <input
              className="text-body-medium w-full outline-none"
              placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              value={inputValue}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              onChange={(e) => setInputValue(e.target.value)}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className={`rounded-rounded flex items-center border border-solid p-2 ${hasText ? 'border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'}`}
          >
            <IconArrowSend className={`${hasText ? 'brightness-0 invert' : ''} h-6 w-6`} />
          </button>
        </div>

        {isFocused && (
          <div className="border-neutral-4 flex w-full flex-col gap-2.5 overflow-y-auto border-t pt-4">
            <div className="flex items-center gap-1.5 self-stretch px-1.5">
              <div className="flex items-center gap-2">
                <SearchOptionButton Icon={IconJira} label="Jira" />
                <SearchOptionButton Icon={IconWiki} label="Wiki" />
                <SearchOptionButton Icon={IconGithub} label="github" />
                <SearchOptionButton Icon={IconSlack} label="Slack" />
              </div>
              <IconDivider />
              <div className="flex items-center gap-2">
                <SearchOptionButton Icon={IconPerson} label="담당자" />
                <SearchOptionButton Icon={IconTag} label="부서명" />
                <SearchOptionButton Icon={IconSpace} label="프로젝트" />
              </div>
              <div className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
                <IconArrowRight />
              </div>
            </div>
            <div className="flex flex-[1_0_0] flex-col items-start gap-4 self-stretch">
              <SearchSuggestion title="최근 질문" />
              <SearchSuggestion title="최근 확인한 지라 티켓" />
              <SearchSuggestion title="캐치업에서 열어본 파일" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
