'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import IconAdd from '@/public/icons/icon/add_small.svg';
import IconArrowSend from '@/public/icons/icon/arrow_send.svg';
import IconJira from '@/public/icons/logo/Jira.svg';
import IconGithub from '@/public/icons/logo/GitHub.svg';
import IconDivider from '@/public/icons/icon/divider.svg';
import IconPerson from '@/public/icons/icon/person.svg';
import IconTag from '@/public/icons/icon/tag.svg';
import IconSpace from '@/public/icons/icon/space.svg';
import IconLock from '@/public/icons/icon/lock_filled.svg';
import IconFile from '@/public/icons/icon/file_filled.svg';
import IconFolder from '@/public/icons/icon/folder_blue.svg';
import IconJiraTicket from '@/public/icons/jira/Task.svg';
import IconJiraSprint from '@/public/icons/jira/Epic.svg';

import { SearchOptionButton, SearchOptionDisabledButton } from '@/components/UI/SearchOptionButton';
import { useEscapeKey } from '@/hooks/useEscapeKey';
import { useOutsideClick } from '@/hooks/useOutsideClick';
import { useUserStore } from '@/store/userStore';
import { SearchOptionPopover } from '@/components/search/SearchOptionPopover';
import { DEPARTMENT_OPTIONS, PERSON_OPTIONS, PROJECT_OPTIONS } from '@/components/search/OptionDummyData';
import { OptionListPopover } from '@/components/search/OptionListPopover';

import { GithubExplorer } from '@/components/search/GithubExplorer';
import { DefaultSearchContent } from '@/components/search/DefaultSearchContent';
import { SelectedFilterChips } from '@/components/search/SelectedFilterChips';
import { GithubNode } from '@/constants/githubRepoData';
import { JiraExplorer } from '@/components/search/JiraExplorer';
import { JiraNode } from '@/constants/jiraData';

export default function Search() {
  const router = useRouter();
  const user = useUserStore((state) => state.user);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [inputValue, setInputValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);

  const [openPopover, setOpenPopover] = useState<'person' | 'department' | 'project' | null>(null);
  const [selectedPeople, setSelectedPeople] = useState<string[]>([]);
  const [selectedDepts, setSelectedDepts] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);

  const [currentRepo, setCurrentRepo] = useState<any>(null);

  const [selectedGithubItems, setSelectedGithubItems] = useState<GithubNode[]>([]);

  const [currentJiraProject, setCurrentJiraProject] = useState<any>(null);
  const [selectedJiraItems, setSelectedJiraItems] = useState<any[]>([]);

  const hasText = inputValue.trim().length > 0;
  const isGithubMode = selectedOptions.includes('Github');
  const isJiraMode = selectedOptions.includes('Jira');

  const togglePerson = (val: string) =>
    setSelectedPeople((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  const toggleDept = (val: string) =>
    setSelectedDepts((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));
  const toggleProject = (val: string) =>
    setSelectedProjects((p) => (p.includes(val) ? p.filter((i) => i !== val) : [...p, val]));

  const getAllChildIds = (node: GithubNode, ids: string[] = []) => {
    ids.push(node.id);
    if (node.children) {
      node.children.forEach((child) => getAllChildIds(child, ids));
    }
    return ids;
  };

  const getAllJiraChildIds = (node: JiraNode, ids: string[] = []) => {
    ids.push(node.id);
    if (node.children) {
      node.children.forEach((child) => getAllJiraChildIds(child, ids));
    }
    return ids;
  };

  const toggleGithubItem = (item: GithubNode) => {
    setSelectedGithubItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);

      if (exists) {
        const idsToRemove = getAllChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      } else {
        return [...prev, item];
      }
    });
  };
  const toggleJiraItem = (item: JiraNode) => {
    setSelectedJiraItems((prev) => {
      const exists = prev.find((i) => i.id === item.id);

      if (exists) {
        const idsToRemove = getAllJiraChildIds(item);
        return prev.filter((i) => !idsToRemove.includes(i.id));
      } else {
        return [...prev, item];
      }
    });
  };
  const handleJiraClick = () => {
    setSelectedOptions((prev) => {
      if (prev.includes('Jira')) {
        setCurrentJiraProject(null);
        return prev.filter((opt) => opt !== 'Jira');
      }
      setIsFocused(true);
      return [...prev.filter((opt) => opt !== 'Github'), 'Jira'];
    });
  };

  const handleGithubClick = () => {
    setSelectedOptions((prev) => {
      if (prev.includes('Github')) {
        setCurrentRepo(null);
        return prev.filter((opt) => opt !== 'Github');
      }
      setIsFocused(true);
      return [...prev.filter((opt) => opt !== 'Jira'), 'Github'];
    });
  };
  const handleResetAll = () => {
    setSelectedPeople([]);
    setSelectedDepts([]);
    setSelectedProjects([]);
    setSelectedGithubItems([]);
    setSelectedJiraItems([]);
  };

  const handleSubmit = () => {
    if (!inputValue.trim()) return;
    const repoQuery = currentRepo ? `&repo=${currentRepo.id}` : '';
    const newSessionId = crypto.randomUUID();
    router.push(`/ragAnswer/${newSessionId}?q=${encodeURIComponent(inputValue)}${repoQuery}`);
  };

  const allSelectedChips = [
    ...selectedPeople.map((name) => ({ id: name, name, Icon: IconPerson, onRemove: () => togglePerson(name) })),
    ...selectedDepts.map((name) => ({ id: name, name, Icon: IconTag, onRemove: () => toggleDept(name) })),
    ...selectedProjects.map((name) => ({ id: name, name, Icon: IconSpace, onRemove: () => toggleProject(name) })),
    ...selectedGithubItems
      .filter((item) => {
        const isParentSelected = selectedGithubItems.some((potentialParent) => {
          if (potentialParent.id === item.id) return false;
          return potentialParent.children?.some((child: any) => child.id === item.id);
        });
        return !isParentSelected;
      })
      .map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'repo' ? IconGithub : item.type === 'tree' ? IconFolder : IconFile,
        onRemove: () => toggleGithubItem(item),
      })),

    ...selectedJiraItems
      .filter((item) => {
        const isParentSelected = selectedJiraItems.some((potentialParent) => {
          if (potentialParent.id === item.id) return false;
          return potentialParent.children?.some((child: any) => child.id === item.id);
        });
        return !isParentSelected;
      })
      .map((item) => ({
        id: item.id,
        name: item.name,
        Icon: item.type === 'project' ? IconJira : item.type === 'board' ? IconJiraSprint : IconJiraTicket,
        onRemove: () => toggleJiraItem(item),
      })),
  ];

  const personLabel = selectedPeople.length > 0 ? `담당자: ${selectedPeople[0]} 외` : '담당자';
  const deptLabel = selectedDepts.length > 0 ? `부서: ${selectedDepts[0]} 외` : '부서명';
  const projectLabel = selectedProjects.length > 0 ? `프로젝트: ${selectedProjects[0]} 외` : '프로젝트';
  const gitLabel = selectedGithubItems.length > 0 ? `Github: ${selectedGithubItems[0].name} 외` : `Github`;
  const jiraLabel = selectedJiraItems.length > 0 ? `Jira: ${selectedJiraItems[0].name} 외` : 'Jira';

  useEscapeKey(() => {
    setIsFocused(false);
    inputRef.current?.blur();
  });
  useOutsideClick(containerRef, () => {
    if (hasText) return;
    if (openPopover !== null) return;
    setIsFocused(false);
    inputRef.current?.blur();
  });

  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = 'auto';
    inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 26 * 6) + 'px';
  }, [inputValue]);

  return (
    <div className="flex flex-col items-center gap-4 self-stretch pt-16 pb-16">
      <div className="flex h-24 flex-col items-center justify-center gap-3 text-gray-50">
        <div className="text-display-xlarge text-normal-normal">반갑습니다, {user?.name}님!</div>
        <div className="text-heading-large text-normal-alternative">
          무엇을 도와드릴까요? 필요한 업무정보를 찾아보세요.
        </div>
      </div>

      <div
        ref={containerRef}
        className={`shadow-rag-bar border-neutral-4 flex w-190 flex-col items-center gap-1.5 border border-solid bg-white ${
          isFocused ? 'h-125.5 max-h-135 min-h-92.5 overflow-hidden rounded-[28px] p-3' : 'rounded-rounded h-auto p-3'
        }`}
      >
        <div className="flex w-full items-end justify-between">
          <div className="text-button-secondary-mono relative bottom-0.5 mr-2 flex h-10 w-10 cursor-pointer items-center justify-center p-1.5">
            <IconAdd className="text-gray-70 h-7 w-7" />
          </div>
          <div className="flex flex-1 items-center gap-2">
            <textarea
              ref={inputRef}
              rows={1}
              onBlur={(e) => {
                if (containerRef.current?.contains(e.relatedTarget as Node)) {
                  setIsFocused(true); // 다시 포커스 강제
                  return;
                }
                if (!hasText) setIsFocused(false);
              }}
              className="text-body-medium mb-2.25 w-full resize-none outline-none"
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
            className={`rounded-rounded relative bottom-px ml-2 flex items-center border border-solid p-2 ${
              hasText ? 'cursor-pointer border-blue-50 bg-blue-50' : 'bg-neutral-1 border-neutral-2'
            }`}
          >
            <IconArrowSend className={`${hasText ? 'brightness-0 invert' : 'text-gray-30'} h-6 w-6`} />
          </button>
        </div>

        {isFocused && (
          <div className="border-neutral-4 mt-1 flex min-h-0 w-full flex-1 flex-col gap-0 overflow-hidden border-t pt-2">
            <div className="flex items-center gap-1.5 self-stretch overflow-x-scroll px-1.5 whitespace-nowrap">
              <div className="flex items-center gap-2">
                <SearchOptionButton
                  Icon={IconJira}
                  label={jiraLabel}
                  selected={selectedJiraItems.length > 0}
                  onClick={handleJiraClick}
                />
                <SearchOptionButton
                  Icon={IconGithub}
                  label={gitLabel}
                  selected={selectedGithubItems.length > 0}
                  onClick={handleGithubClick}
                />
                <SearchOptionDisabledButton Icon={IconLock} label="Wiki" />
                <SearchOptionDisabledButton Icon={IconLock} label="Slack" />
              </div>
              <IconDivider className="text-gray-5 h-6 w-6 shrink-0" />

              <div className="flex items-center gap-2">
                <SearchOptionPopover
                  open={openPopover === 'person'}
                  onOpenChange={(o) => {
                    setOpenPopover(o ? 'person' : null);
                    if (!o) inputRef.current?.focus();
                  }}
                  trigger={
                    <SearchOptionButton
                      Icon={IconPerson}
                      label={personLabel}
                      selected={selectedPeople.length > 0}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => setOpenPopover('person')}
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
                  onOpenChange={(o) => {
                    setOpenPopover(o ? 'department' : null);
                    if (!o) inputRef.current?.focus();
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
                  onOpenChange={(o) => {
                    setOpenPopover(o ? 'project' : null);
                    if (!o) inputRef.current?.focus();
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
            </div>

            <SelectedFilterChips chips={allSelectedChips} onReset={handleResetAll} />

            <div className="no-scrollbar flex min-h-0 flex-1 flex-col items-start gap-2 self-stretch overflow-y-auto pt-2">
              {isGithubMode ? (
                <GithubExplorer
                  selectedItems={selectedGithubItems.map((i) => i.id)}
                  onToggleItem={toggleGithubItem}
                  currentRepo={currentRepo}
                  onNavigate={setCurrentRepo}
                  onClickBack={handleGithubClick}
                />
              ) : isJiraMode ? (
                <JiraExplorer
                  selectedItems={selectedJiraItems.map((i) => i.id)}
                  onToggleItem={toggleJiraItem}
                  currentProject={currentJiraProject}
                  onNavigate={setCurrentJiraProject}
                  onClickBack={handleJiraClick}
                />
              ) : (
                <DefaultSearchContent />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
