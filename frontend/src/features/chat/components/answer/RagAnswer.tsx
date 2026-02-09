'use client';

import { useCallback, useMemo,useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';

import GithubPRStepSkeleton from '@/features/chat/components/skeleton/GithubPRStepSkeleton';
import RagAnswerSkeleton from '@/features/chat/components/skeleton/RagAnswerSkeleton';
import { TEAM_SPACES } from '@/features/chat/constants/config';
import type { QAPair } from '@/features/chat/utils/chat';
import { formatMarkdownString } from '@/features/chat/utils/markdown';
import { Tooltip, TooltipContent,TooltipTrigger } from '@/shared/components/ui/ToolTip';
import { cn } from '@/shared/utils/cn';

import AnswerActionButtons from './actions/AnswerActionButtons';
import AnswerError from './actions/AnswerError';
import FeedbackSection from './actions/FeedbackSection';
import DateFilter from './filter/DateFilter';
import TeamSpaceModal from './filter/TeamSpaceModal';
import { MarkDownComponents } from './markdown/MarkDownComponents';

import Copy from '/public/icons/icon/copy.svg';
import Divider from '/public/icons/icon/divider.svg';
import DropDown from '/public/icons/icon/dropdown_down.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Share from '/public/icons/icon/share_2.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';

const ANSWER_ICONS = [
  { name: 'Copy', icon: Copy },
  { name: 'Share', icon: Share },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
  { name: 'Kebeb', icon: Kebeb },
];

interface RagAnswerProps {
  currentQA: QAPair | undefined;
  sessionId: string;
  isLoading: boolean;
  isError: boolean;
  currentStep: RagUIStepKey;
  showPRSelection: boolean;
  prList: PRPayload[];
  onPRContinue: (selectedPrNumbers: number[]) => Promise<void>;
  onPRRefetch: () => Promise<void>;
  onFeedbackSubmitted: (messageId: string) => void;
  answerScrollRef: React.RefObject<HTMLDivElement | null>;
  feedbackRef: React.RefObject<HTMLDivElement | null>;
}

const RagAnswer = ({
  currentQA,
  sessionId,
  isLoading,
  isError,
  currentStep,
  showPRSelection,
  prList,
  onPRContinue,
  onPRRefetch,
  onFeedbackSubmitted,
  answerScrollRef,
  feedbackRef,
}: RagAnswerProps) => {
  // 섹션 로컬 UI 상태
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const [filterOpenMap, setFilterOpenMap] = useState<Record<string, boolean>>({});
  const [spaceDropDownOpenMap, setSpaceDropDownOpenMap] = useState<Record<string, boolean>>({});
  const [selectedTeamSpaceId, setSelectedTeamSpaceId] = useState<string>(TEAM_SPACES[0].id);

  const selectedTeamSpace = useMemo(
    () => TEAM_SPACES.find((t) => t.id === selectedTeamSpaceId) ?? TEAM_SPACES[0],
    [selectedTeamSpaceId],
  );

  const toggleSpaceDropdown = useCallback((answerId: string) => {
    setSpaceDropDownOpenMap((prev) => {
      const nextOpen = !prev?.[answerId];
      return nextOpen ? { [answerId]: true } : {};
    });
  }, []);

  const closeSpaceDropdown = useCallback((answerId: string) => {
    setSpaceDropDownOpenMap((prev) => {
      if (!prev?.[answerId]) return prev;
      const copied = { ...prev };
      delete copied[answerId];
      return copied;
    });
  }, []);

  // 답변이 있는 경우
  if (currentQA?.answer) {
    const answerId = currentQA.answer.id;
    const isFilterOpen = filterOpenMap[answerId];
    const isSpaceOpen = spaceDropDownOpenMap?.[answerId];

    return (
      <div ref={answerScrollRef} className="flex-1 overflow-y-auto">
        <div className="flex flex-col gap-2">
          {/* 필터/팀스페이스 드롭다운 */}
          {currentQA.answer.content && (
            <div className="mb-3 rounded-xl">
              {!isFilterOpen ? (
                <div className="relative flex items-center gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSpaceDropdown(answerId);
                        }}
                        className={cn(
                          'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                          isSpaceOpen && 'bg-neutral-3 rounded-lg',
                        )}
                      >
                        <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                          {selectedTeamSpace.name}
                        </div>
                        <DropDown
                          className={cn(
                            'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                            isSpaceOpen && 'rotate-180',
                          )}
                        />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>답변 기준 팀스페이스 변경하기</TooltipContent>
                  </Tooltip>

                  {isSpaceOpen && (
                    <div className="absolute top-10.5 z-100">
                      <TeamSpaceModal
                        onClose={() => closeSpaceDropdown(answerId)}
                        teamSpaces={[...TEAM_SPACES]}
                        selectedId={selectedTeamSpace.id}
                        onSelect={(team) => setSelectedTeamSpaceId(team.id)}
                      />
                    </div>
                  )}

                  <Divider className="text-neutral-4 h-6 w-6 shrink-0" />

                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
                    <button
                      onClick={() => setFilterOpenMap((prev) => ({ ...prev, [answerId]: true }))}
                      className="cursor-pointer"
                    >
                      <ToggleOff className="h-5 w-9" />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="relative flex gap-1">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSpaceDropdown(answerId);
                          }}
                          className={cn(
                            'flex cursor-pointer items-center gap-1 px-2 py-1',
                            isSpaceOpen ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                          )}
                        >
                          <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                            {selectedTeamSpace.name}
                          </div>
                          <DropDown
                            className={cn(
                              'text-gray-70 relative h-4 w-4 shrink-0',
                              isSpaceOpen ? 'rotate-180 rounded-lg' : 'bottom-px',
                            )}
                          />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>답변 기준 팀스페이스 변경하기</TooltipContent>
                    </Tooltip>

                    {isSpaceOpen && (
                      <div className="absolute top-10.5 z-100">
                        <TeamSpaceModal
                          onClose={() => closeSpaceDropdown(answerId)}
                          teamSpaces={[...TEAM_SPACES]}
                          selectedId={selectedTeamSpace.id}
                          onSelect={(team) => setSelectedTeamSpaceId(team.id)}
                        />
                      </div>
                    )}
                  </div>

                  <DateFilter
                    isOpen={isFilterOpen}
                    onClose={() => setFilterOpenMap((prev) => ({ ...prev, [answerId]: false }))}
                  />
                </div>
              )}
            </div>
          )}

          {currentQA.answer.content ? (
            <>
              {/* 마크다운 답변 */}
              <div className="markdown-body max-w-192.75 wrap-break-words">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={MarkDownComponents(currentQA.answer.sources)}
                >
                  {formatMarkdownString(currentQA.answer.content)}
                </ReactMarkdown>
              </div>

              <div className="text-body-small text-gray-30">
                질문과 연관된 {currentQA.answer.sources?.length || 0}개의 핵심 자료를 선별했어요.
              </div>

              {/* 액션 버튼 */}
              <AnswerActionButtons
                icons={ANSWER_ICONS}
                messageId={currentQA.answer.id}
                feedbackVisibleMap={feedbackVisibleMap}
                setFeedbackVisibleMap={setFeedbackVisibleMap}
              />

              {/* 피드백 */}
              <div ref={feedbackRef}>
                <FeedbackSection
                  messageId={currentQA.answer.id}
                  chatHistoryId={currentQA.answer.chatHistoryId}
                  hasFeedback={currentQA.answer.hasFeedback}
                  feedbackVisibleMap={feedbackVisibleMap}
                  setFeedbackVisibleMap={setFeedbackVisibleMap}
                  onFeedbackSubmitted={onFeedbackSubmitted}
                />
              </div>
            </>
          ) : (
            <AnswerError
              icons={ANSWER_ICONS}
              messageId={`error_${sessionId}`}
              hasFeedback={currentQA.answer.hasFeedback}
              feedbackVisibleMap={feedbackVisibleMap}
              setFeedbackVisibleMap={setFeedbackVisibleMap}
            />
          )}
        </div>
      </div>
    );
  }

  // 답변이 없는 경우 (로딩/PR선택/에러)
  return (
    <div ref={answerScrollRef} className="flex-1 overflow-y-auto">
      {showPRSelection && (
        <GithubPRStepSkeleton
          onContinue={onPRContinue}
          prList={prList}
          onRefetch={onPRRefetch}
        />
      )}
      {isLoading && !currentQA?.answer && (
        <RagAnswerSkeleton currentStep={currentStep} />
      )}
      {isError && (
        <AnswerError
          icons={ANSWER_ICONS}
          messageId={`error_${sessionId}`}
          feedbackVisibleMap={feedbackVisibleMap}
          setFeedbackVisibleMap={setFeedbackVisibleMap}
        />
      )}
    </div>
  );
};

export default RagAnswer;
