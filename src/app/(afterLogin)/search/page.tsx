'use client';

import { useState, useRef, useEffect } from 'react';
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
import IconLock from '@/public/icons/icon/lock_filled.svg';
import IconCloseSmall from '@/public/icons/icon/cancel_small.svg';
import IconReset from '@/public/icons/icon/reset.svg';

import { FilterChip } from '@/components/UI/SearchFilter';
import { SearchOptionButton, SearchOptionDisabledButton } from '@/components/UI/SearchOptionButton';
import { SearchSuggestion } from '@/components/UI/SearchSuggestion';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import DropdownModal from '@/components/modal/DropdownModal';
import { useUserStore } from '@/store/userStore';
import { RECOMMAND_QUESTIONS } from '@/constants/recommandQuestion';
import { SearchOptionPopover } from '@/components/search/SearchOptionPopover';
import { DEPARTMENT_OPTIONS, PERSON_OPTIONS, PROJECT_OPTIONS } from '@/components/search/OptionDummyData';
import { OptionListPopover } from '@/components/search/OptionListPopover';

export default function Search() {
  const router = useRouter();

  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);

  const currentSuggestions = selectedRepoId ? RECOMMAND_QUESTIONS[selectedRepoId] || [] : [];

  const [openPopover, setOpenPopover] = useState<'person' | 'department' | 'project' | null>(null);

  const [selectedSystems, setSelectedSystems] = useState<string[]>([]);
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);

  const toggleSystem = (val: string) =>
    setSelectedSystems((prev) => (prev.includes(val) ? prev.filter((i) => i !== val) : [...prev, val]));

  const togglePerson = (val: string) =>
    setSelectedPeople((prev) => (prev.includes(val) ? prev.filter((i) => i !== val) : [...prev, val]));

  const toggleDept = (val: string) =>
    setSelectedDepts((prev) => (prev.includes(val) ? prev.filter((i) => i !== val) : [...prev, val]));

  const toggleProject = (val: string) =>
    setSelectedProjects((prev) => (prev.includes(val) ? prev.filter((i) => i !== val) : [...prev, val]));

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

  const personLabel =
    selectedPeople.length > 0
      ? `담당자: ${selectedPeople[0]}${selectedPeople.length > 1 ? ` 외 ${selectedPeople.length - 1}명` : ''}`
      : '담당자';

  const deptLabel =
    selectedDepts.length > 0
      ? `부서: ${selectedDepts[0]}${selectedDepts.length > 1 ? ` 외 ${selectedDepts.length - 1}명` : ''}`
      : '부서명';

  const projectLabel =
    selectedProjects.length > 0
      ? `프로젝트: ${selectedProjects[0]}${selectedProjects.length > 1 ? ` 외 ${selectedProjects.length - 1}명` : ''}`
      : '프로젝트';

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const user = useUserStore((state) => state.user);

  useEscapeKey(() => {
    setIsFocused(false);
    inputRef.current?.blur();
  });

  useOutsideClick(containerRef, () => {
    if (openPopover || isGithubModalOpen || hasText) return;
    setIsFocused(false);
    inputRef.current?.blur();
  });

  const toggleOption = (label: string) => {
    setSelectedOptions((prev) => (prev.includes(label) ? prev.filter((item) => item !== label) : [...prev, label]));
  };

  const allSelectedChips = [
    ...selectedPeople.map((name) => ({
      id: name,
      name,
      category: 'person',
      Icon: IconPerson,
      onRemove: () => togglePerson(name),
    })),
    ...selectedDepts.map((name) => ({
      id: name,
      name,
      category: 'dept',
      Icon: IconTag,
      onRemove: () => toggleDept(name),
    })),
    ...selectedProjects.map((name) => ({
      id: name,
      name,
      category: 'project',
      Icon: IconSpace,
      onRemove: () => toggleProject(name),
    })),
  ];

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

  const handleResetAll = () => {
    setSelectedSystems([]);
    setSelectedPeople([]);
    setSelectedDepts([]);
    setSelectedProjects([]);
    setSelectedRepoId(null);
    setSelectedOptions((prev) => prev.filter((opt) => opt === 'Github' && !selectedRepoId));
  };

  const hasText = inputValue.trim().length > 0;

  useEffect(() => {
    if (!inputRef.current) return;

    const el = inputRef.current;
    el.style.height = 'auto';

    const lineHeight = 26;
    const maxHeight = lineHeight * 6;

    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px';
  }, [inputValue]);

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
        <div className="flex w-full items-end justify-between">
          <div className="mr-2 flex h-10 w-10 items-center justify-center p-1.5">
            <IconAdd className="h-6 w-6" />
          </div>
          <div className="flex flex-1 items-center gap-2">
            <textarea
              ref={inputRef}
              rows={1}
              onBlur={() => {
                if (hasText) setIsFocused(true);
              }}
              className="text-body-medium mb-1.5 w-full resize-none outline-none"
              placeholder="업무 흐름이나 인수인계 내용을 질문해보세요"
              value={inputValue}
              onFocus={() => setIsFocused(true)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              onChange={(e) => setInputValue(e.target.value)}
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className={`rounded-rounded ml-2 flex items-center border border-solid p-2 ${hasText ? 'border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'}`}
          >
            <IconArrowSend className={`${hasText ? 'brightness-0 invert' : ''} h-6 w-6`} />
          </button>
        </div>

        {isFocused && (
          <div className="border-neutral-4 flex w-full flex-col gap-2.5 overflow-visible border-t pt-4">
            <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
              <div className="flex items-center gap-2">
                <SearchOptionButton
                  Icon={IconJira}
                  label="Jira"
                  selected={selectedOptions.includes('Jira')}
                  onClick={() => toggleOption('Jira')}
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
                <SearchOptionDisabledButton Icon={IconLock} label="Wiki" />
                <SearchOptionDisabledButton Icon={IconLock} label="Slack" />
              </div>
              <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />
              <div className="flex items-center gap-2">
                <SearchOptionPopover
                  open={openPopover === 'person'}
                  onOpenChange={(open) => {
                    setOpenPopover(open ? 'person' : null);
                    if (!open) inputRef.current?.focus();
                  }}
                  trigger={
                    <SearchOptionButton
                      Icon={IconPerson}
                      label={personLabel}
                      selected={selectedPeople.length > 0}
                      onMouseDown={(e) => {
                        e.preventDefault();
                      }}
                      onClick={() => {
                        setOpenPopover('person');
                        inputRef.current?.focus();
                      }}
                    />
                  }
                >
                  <OptionListPopover
                    title="담당자 선택"
                    options={PERSON_OPTIONS}
                    selected={selectedPeople}
                    onToggle={togglePerson}
                    Icon={IconPerson}
                  />
                </SearchOptionPopover>
                <SearchOptionPopover
                  open={openPopover === 'department'}
                  onOpenChange={(open) => {
                    setOpenPopover(open ? 'department' : null);
                    if (!open) inputRef.current?.focus();
                  }}
                  trigger={
                    <SearchOptionButton
                      Icon={IconTag}
                      label={deptLabel}
                      selected={selectedDepts.length > 0}
                      onMouseDown={(e) => e.preventDefault()}
                    />
                  }
                >
                  <OptionListPopover
                    title="부서"
                    options={DEPARTMENT_OPTIONS}
                    selected={selectedDepts}
                    onToggle={toggleDept}
                    Icon={IconTag}
                  />
                </SearchOptionPopover>

                <SearchOptionPopover
                  open={openPopover === 'project'}
                  onOpenChange={(open) => {
                    setOpenPopover(open ? 'project' : null);
                    if (!open) inputRef.current?.focus();
                  }}
                  trigger={
                    <SearchOptionButton
                      Icon={IconSpace}
                      label={projectLabel}
                      selected={selectedProjects.length > 0}
                      onMouseDown={(e) => e.preventDefault()}
                    />
                  }
                >
                  <OptionListPopover
                    title="프로젝트"
                    options={PROJECT_OPTIONS}
                    selected={selectedProjects}
                    onToggle={toggleProject}
                    Icon={IconSpace}
                  />
                </SearchOptionPopover>
              </div>
              <div className="flex h-7 w-7 items-center justify-center gap-2.5 p-0.5">
                <IconArrowRight className="h-5 w-5 shrink-0" />
              </div>
            </div>
            {allSelectedChips.length > 0 && (
              <div className="bg-neutral-1 border-neutral-2 flex w-full flex-col gap-2 rounded-xl border p-2">
                <div className="flex w-full items-center justify-between px-1 pb-1">
                  <div className="text-body-xsmall text-nomal-alternative">
                    선택 항목 &nbsp;{allSelectedChips.length}
                  </div>
                  <button
                    onClick={handleResetAll}
                    className="rounded-rounded bg-neutral-3 flex items-center justify-center p-0.5"
                  >
                    <IconReset className="h-4.5 w-4.5" />
                  </button>
                </div>

                <div className="no-scrollbar flex w-full gap-1.5 overflow-x-auto whitespace-nowrap">
                  {allSelectedChips.map((chip) => {
                    const ChipIcon = chip.Icon;
                    return (
                      <div
                        key={`${chip.category}-${chip.id}`}
                        className="border-neutral-5 rounded-rounded flex h-[37px] shrink-0 items-center gap-1 border bg-white p-1.5"
                      >
                        <div className="border-neutral-3 bg-neutral-1 rounded-rounded flex h-6.25 w-6.25 shrink-0 items-center justify-center border">
                          <ChipIcon className="text-gray-70 h-4 w-4" />
                        </div>

                        <span className="text-body-small text-gray-80 ml-0.5 max-w-30 truncate">{chip.name}</span>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            chip.onRemove();
                          }}
                          className="hover:text-blue-80 ml-0.5 transition-colors"
                        >
                          <IconCloseSmall className="h-5 w-5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
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
