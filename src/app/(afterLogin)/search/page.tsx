'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
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
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import DropdownModal from '@/components/modal/DropdownModal';
import { useUserStore } from '@/store/userStore';
import { RECOMMAND_QUESTIONS } from '@/constants/recommandQuestion';

export default function Search() {
  const router = useRouter();

  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);

  const currentSuggestions = selectedRepoId ? RECOMMAND_QUESTIONS[selectedRepoId] || [] : [];

  const handleSuggestionClick = (question: string) => {
    setInputValue(question);
    inputRef.current?.focus();
  };
  const gitToggleOption = (label: string) => {
    setSelectedOptions((prev) => (prev.includes(label) ? prev.filter((item) => item !== label) : [...prev, label]));
  };

  const handleGithubClick = () => {
    if (selectedOptions.includes('Github')) {
      toggleOption('Github');
      setSelectedRepoId(null);
    } else {
      setIsGithubModalOpen(true);
    }
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const user = useUserStore((state) => state.user);

  useEscapeKey(() => {
    setIsFocused(false);
    inputRef.current?.blur();
  });

  useOutsideClick(containerRef, () => {
    setIsFocused(false);
    inputRef.current?.blur();
  });

  const toggleOption = (label: string) => {
    setSelectedOptions((prev) => (prev.includes(label) ? prev.filter((item) => item !== label) : [...prev, label]));
  };

  const handleSubmit = () => {
    if (!inputValue.trim()) return;

    if (selectedOptions.includes('Github') && !selectedRepoId) {
      alert('레포지토리를 선택해주세요.');
      setIsGithubModalOpen(true);
      return;
    }

    const newSessionId = crypto.randomUUID();
    const githubQuery = selectedRepoId ? `&repo=${selectedRepoId}` : '';
    router.push(`/ragAnswer/${newSessionId}?q=${encodeURIComponent(inputValue)}${githubQuery}`);
  };

  const hasText = inputValue.trim().length > 0;

  return (
    <div className="flex flex-col items-center gap-4 self-stretch pt-16 pb-16">
      <div className="flex h-24 flex-col items-center justify-center gap-3">
        <div className="text-display-xlarge text-nomal-normal">반갑습니다, {user?.name}님!</div>
        <div className="text-heading-large text-nomal-alternative">
          무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
        </div>
      </div>
      <div className="text-blue-55 text-body-small flex items-center gap-2.5">
        {/* {['연차 신청 방법', '권한 신청 방법', '피그마 관련 내부 그라운드 룰', '데이터 요청 방법'].map((text) => (
          <FilterChip key={text} label={text} />
        ))} */}
      </div>
      <div
        ref={containerRef}
        className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-2.5 border border-solid bg-white ${isFocused ? 'h-125.5 max-h-135 min-h-92.5 rounded-[28px] p-3 px-4' : 'rounded-rounded h-auto p-3 px-4'} `}
      >
        <div className="flex w-full items-center justify-between">
          <div className="flex flex-1 items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center p-1.5">
              <IconAdd className="h-6 w-6" />
            </div>
            <input
              ref={inputRef}
              className="text-body-medium w-full outline-none"
              placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
              value={inputValue}
              onFocus={() => setIsFocused(true)}
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
          <div
            onMouseDown={(e) => e.preventDefault()}
            className="border-neutral-4 flex w-full flex-col gap-2.5 overflow-visible border-t pt-4"
          >
            <div className="flex items-center gap-1.5 self-stretch px-1.5 whitespace-nowrap">
              <div className="flex items-center gap-2">
                <SearchOptionButton
                  Icon={IconJira}
                  label="Jira"
                  selected={selectedOptions.includes('Jira')}
                  onClick={() => toggleOption('Jira')}
                />
                <SearchOptionButton
                  Icon={IconWiki}
                  label="Wiki"
                  selected={selectedOptions.includes('Wiki')}
                  onClick={() => toggleOption('Wiki')}
                />
                <div className="relative">
                  <SearchOptionButton
                    Icon={IconGithub}
                    label={selectedRepoId ? 'Github' + ':' + selectedRepoId : 'Github'}
                    selected={selectedOptions.includes('Github')}
                    onClick={handleGithubClick}
                  />
                  {isGithubModalOpen && (
                    <div className="absolute top-full left-0 z-[100] mt-2">
                      <DropdownModal
                        onClose={() => setIsGithubModalOpen(false)}
                        onSelect={(id) => {
                          setSelectedRepoId(id);
                          if (!selectedOptions.includes('Github')) {
                            gitToggleOption('Github');
                          }
                          setIsGithubModalOpen(false);
                        }}
                      />
                    </div>
                  )}
                </div>
                <SearchOptionButton
                  Icon={IconSlack}
                  label="Slack"
                  selected={selectedOptions.includes('Slack')}
                  onClick={() => toggleOption('Slack')}
                />
              </div>
              <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
              <div className="flex items-center gap-2">
                <SearchOptionButton
                  Icon={IconPerson}
                  label="담당자"
                  selected={selectedOptions.includes('담당자')}
                  onClick={() => toggleOption('담당자')}
                />
                <SearchOptionButton
                  Icon={IconTag}
                  label="부서명"
                  selected={selectedOptions.includes('부서명')}
                  onClick={() => toggleOption('부서명')}
                />
                <SearchOptionButton
                  Icon={IconSpace}
                  label="프로젝트"
                  selected={selectedOptions.includes('프로젝트')}
                  onClick={() => toggleOption('프로젝트')}
                />
              </div>
              <div className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
                <IconArrowRight />
              </div>
            </div>
            <div className="flex flex-[1_0_0] flex-col items-start gap-4 self-stretch">
              {selectedRepoId && currentSuggestions.length > 0 && (
                <div className="border-neutral-1 flex flex-[1_0_0] flex-col items-start gap-4 self-stretch border-t pt-4">
                  <SearchSuggestion
                    title="레포지토리 맞춤 질문"
                    suggestions={currentSuggestions}
                    onItemClick={(question) => setInputValue(question)}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
