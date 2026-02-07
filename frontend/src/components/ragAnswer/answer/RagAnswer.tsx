'use client';

import { useState, useCallback, useMemo } from 'react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

import type { QAPair } from '@/util/ragAnswer/chat';
import { formatMarkdownString } from '@/util/ragAnswer/markdown';
import { TEAM_SPACES } from '@/constants/ragAnswer/config';

import RagAnswerSkeleton from '@/components/Skeleton/RagAnswerSkeleton';
import GithubPRStepSkeleton from '@/components/Skeleton/GithubPRStepSkeleton';
import AnswerError from './AnswerError';
import AnswerActionButtons from './AnswerActionButtons';
import FeedbackSection from './FeedbackSection';
import DateFilter from './DateFilter';
import TeamSpaceModal from './TeamSpaceModal';
import ToolTip from '@/components/shared/ToolTip';
import { MarkDownComponents } from './markdown/MarkDownComponents';

import Divider from '/public/icons/icon/divider.svg';
import DropDown from '/public/icons/icon/dropdown_down.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';
import Copy from '/public/icons/icon/copy.svg';
import Share from '/public/icons/icon/share_2.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

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
                  <div className="group relative flex items-center gap-1">
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSpaceDropdown(answerId);
                      }}
                      className={clsx(
                        'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                        isSpaceOpen && 'bg-neutral-3 rounded-lg',
                      )}
                    >
                      <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                        {selectedTeamSpace.name}
                      </div>
                      <DropDown
                        className={clsx(
                          'text-gray-70 relative bottom-px h-4 w-4 shrink-0',
                          isSpaceOpen && 'rotate-180',
                        )}
                      />
                    </div>
                    <div className="absolute bottom-9.5 left-23.75 z-100">
                      <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                    </div>
                  </div>

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
                      <ToggleOff />
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  <div className="relative flex gap-1">
                    <div className="group relative w-fit gap-1">
                      <div
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSpaceDropdown(answerId);
                        }}
                        className={clsx(
                          'flex cursor-pointer items-center gap-1 px-2 py-1',
                          isSpaceOpen ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                        )}
                      >
                        <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                          {selectedTeamSpace.name}
                        </div>
                        <DropDown
                          className={clsx(
                            'text-gray-70 relative h-4 w-4 shrink-0',
                            isSpaceOpen ? 'rotate-180 rounded-lg' : 'bottom-px',
                          )}
                        />
                      </div>
                      <div className="absolute bottom-9.5 left-23.75">
                        <ToolTip text={'답변 기준 팀스페이스 변경하기'} />
                      </div>
                    </div>

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
              <div className="markdown-body max-w-192.75 break-words">
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
