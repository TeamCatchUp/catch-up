/**
 * Answer Compound Component
 * 답변 영역 (Loading, Content, Actions, Feedback, Error, Filter)
 */

'use client';

import type { PropsWithChildren, ReactNode } from 'react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

import { useRagPageContext } from './Context';
import { formatMarkdownString } from '@/util/ragAnswer/markdown';
import { TEAM_SPACES } from '@/constants/ragAnswer/config';

import RagAnswerSkeleton from '@/components/Skeleton/RagAnswerSkeleton';
import GithubPRStepSkeleton from '@/components/Skeleton/GithubPRStepSkeleton';
import ErrorResponse from '@/components/ragAnswer/components/answerComponent/ErrorResponse';
import AnswerActionButtons from '@/components/ragAnswer/components/answerComponent/AnswerActionButtons';
import FeedbackSection from '@/components/ragAnswer/components/answerComponent/FeedbackSection';
import FilterComponent from '@/components/ragAnswer/components/answerComponent/Filter';
import TeamSpaceModal from '@/components/ragAnswer/components/modal/TeamSpaceModal';
import ToolTip from '@/components/shared/ToolTip';
import { MarkDownComponents } from '@/components/ragAnswer/components/answerComponent/markdown/MarkDownComponents';

import Divider from '/public/icons/icon/divider.svg';
import DropDown from '/public/icons/icon/dropdown_down.svg';
import ToggleOff from '/public/icons/icon/state=Off.svg';
import Copy from '/public/icons/icon/copy.svg';
import Share from '/public/icons/icon/share_2.svg';
import ThumbsDown from '/public/icons/icon/thumbs-down.svg';
import Rotate from '/public/icons/icon/rotate.svg';
import Kebeb from '/public/icons/icon/kebeb 2.svg';

/** 답변 영역 아이콘 목록 */
const ANSWER_ICONS = [
  { name: 'Copy', icon: Copy },
  { name: 'Share', icon: Share },
  { name: 'ThumbsDown', icon: ThumbsDown },
  { name: 'Rotate', icon: Rotate },
  { name: 'Kebeb', icon: Kebeb },
];

/** Answer Root - 스크롤 가능한 답변 컨테이너 */
interface AnswerProps extends PropsWithChildren {
  className?: string;
}

const Answer = ({ children, className }: AnswerProps) => {
  const { refs } = useRagPageContext();

  return (
    <div
      ref={refs.answerScroll}
      className={clsx('flex-1 overflow-y-auto', className)}
    >
      {children}
    </div>
  );
};

/** 로딩 상태 표시 (RAG 단계 스켈레톤) */
const AnswerLoading = () => {
  const { chat, pagination } = useRagPageContext();
  const { currentQA } = pagination;

  // 이미 답변이 있으면 표시하지 않음
  if (currentQA?.answer) return null;
  if (!chat.isLoading) return null;

  return <RagAnswerSkeleton currentStep={chat.currentStep} />;
};

/** PR 선택 단계 표시 */
const AnswerPRSelection = () => {
  const { chat, pagination } = useRagPageContext();
  const { currentQA } = pagination;

  if (currentQA?.answer) return null;
  if (!chat.showPRSelection) return null;

  return (
    <GithubPRStepSkeleton
      onContinue={chat.handlePRContinue}
      prList={chat.prList}
      onRefetch={chat.handlePRRefetch}
    />
  );
};

/** 에러 상태 표시 */
const AnswerError = () => {
  const { chat, pagination, sessionId, ui } = useRagPageContext();
  const { currentQA } = pagination;

  // 답변이 있고 content가 빈 문자열이면 에러
  if (currentQA?.answer?.content) return null;

  // 답변이 없고 에러 상태이면 표시
  if (!currentQA?.answer && chat.isError) {
    return (
      <ErrorResponse
        icons={ANSWER_ICONS}
        messageId={`error_${sessionId}`}
        feedbackVisibleMap={ui.feedbackVisibleMap}
        setFeedbackVisibleMap={ui.setFeedbackVisibleMap}
      />
    );
  }

  // 답변이 있지만 content가 비어있으면 에러
  if (currentQA?.answer && !currentQA.answer.content) {
    return (
      <ErrorResponse
        icons={ANSWER_ICONS}
        messageId={`error_${sessionId}`}
        hasFeedback={currentQA.answer.hasFeedback}
        feedbackVisibleMap={ui.feedbackVisibleMap}
        setFeedbackVisibleMap={ui.setFeedbackVisibleMap}
      />
    );
  }

  return null;
};

/** 필터/팀스페이스 드롭다운 영역 */
const AnswerFilterBar = () => {
  const { pagination, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (!currentQA?.answer) return null;
  if (!currentQA.answer.content) return null;

  const answerId = currentQA.answer.id;
  const isFilterOpen = ui.filterOpenMap[answerId];
  const isSpaceOpen = ui.spaceDropDownOpenMap?.[answerId];

  return (
    <div className="mb-3 rounded-xl">
      {!isFilterOpen ? (
        <div className="relative flex items-center gap-1">
          {/* 팀스페이스 드롭다운 */}
          <div className="group relative flex items-center gap-1">
            <div
              onClick={(e) => {
                e.stopPropagation();
                ui.toggleSpaceDropdown(answerId);
              }}
              className={clsx(
                'icon-button-only-gray flex cursor-pointer items-center gap-1 px-2 py-1',
                isSpaceOpen && 'bg-neutral-3 rounded-lg',
              )}
            >
              <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                {ui.selectedTeamSpace.name}
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
                onClose={() => ui.closeSpaceDropdown(answerId)}
                teamSpaces={[...TEAM_SPACES]}
                selectedId={ui.selectedTeamSpace.id}
                onSelect={(team) => ui.setSelectedTeamSpaceId(team.id)}
              />
            </div>
          )}

          <Divider className="text-neutral-4 h-6 w-6 shrink-0" />

          <div className="flex shrink-0 items-center gap-3">
            <span className="text-body-xsmall text-gray-50">답변 세부 필터</span>
            <button
              onClick={() => ui.setFilterOpenMap((prev) => ({ ...prev, [answerId]: true }))}
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
                  ui.toggleSpaceDropdown(answerId);
                }}
                className={clsx(
                  'flex cursor-pointer items-center gap-1 px-2 py-1',
                  isSpaceOpen ? 'bg-neutral-3 rounded-lg' : 'icon-button-only-gray',
                )}
              >
                <div className="text-body-small text-gray-70 relative top-px block w-32 truncate px-2 py-1">
                  {ui.selectedTeamSpace.name}
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
                  onClose={() => ui.closeSpaceDropdown(answerId)}
                  teamSpaces={[...TEAM_SPACES]}
                  selectedId={ui.selectedTeamSpace.id}
                  onSelect={(team) => ui.setSelectedTeamSpaceId(team.id)}
                />
              </div>
            )}
          </div>

          <FilterComponent
            isOpen={isFilterOpen}
            onClose={() => ui.setFilterOpenMap((prev) => ({ ...prev, [answerId]: false }))}
          />
        </div>
      )}
    </div>
  );
};

/** 마크다운 답변 내용 */
const AnswerContent = () => {
  const { pagination, chat } = useRagPageContext();
  const { currentQA } = pagination;

  if (chat.isLoading || !currentQA?.answer?.content) return null;

  const formattedContent = formatMarkdownString(currentQA.answer.content);

  return (
    <>
      <div className="markdown-body max-w-192.75 break-words">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={MarkDownComponents(currentQA.answer.sources)}
        >
          {formattedContent}
        </ReactMarkdown>
      </div>

      <div className="text-body-small text-gray-30">
        질문과 연관된 {currentQA.answer.sources?.length || 0}개의 핵심 자료를 선별했어요.
      </div>
    </>
  );
};

/** 답변 액션 버튼들 (복사, 공유, 피드백 등) */
const AnswerActions = () => {
  const { pagination, chat, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (chat.isLoading || !currentQA?.answer?.content) return null;

  return (
    <AnswerActionButtons
      icons={ANSWER_ICONS}
      messageId={currentQA.answer.id}
      feedbackVisibleMap={ui.feedbackVisibleMap}
      setFeedbackVisibleMap={ui.setFeedbackVisibleMap}
    />
  );
};

/** 피드백 섹션 */
const AnswerFeedback = () => {
  const { refs, pagination, chat, ui } = useRagPageContext();
  const { currentQA } = pagination;

  if (chat.isLoading || !currentQA?.answer?.content) return null;

  return (
    <div ref={refs.feedback}>
      <FeedbackSection
        messageId={currentQA.answer.id}
        chatHistoryId={currentQA.answer.chatHistoryId}
        hasFeedback={currentQA.answer.hasFeedback}
        feedbackVisibleMap={ui.feedbackVisibleMap}
        setFeedbackVisibleMap={ui.setFeedbackVisibleMap}
        onFeedbackSubmitted={chat.updateMessageFeedback}
      />
    </div>
  );
};

/** 전체 답변 영역 렌더링 헬퍼 */
const AnswerFull = () => {
  const { pagination, chat } = useRagPageContext();
  const { currentQA } = pagination;

  // 답변이 있는 경우
  if (currentQA?.answer) {
    return (
      <div className="flex flex-col gap-2">
        <AnswerFilterBar />
        {currentQA.answer.content ? (
          <>
            <AnswerContent />
            <AnswerActions />
            <AnswerFeedback />
          </>
        ) : (
          <AnswerError />
        )}
      </div>
    );
  }

  // 답변이 없는 경우 (로딩/PR선택/에러)
  return (
    <>
      <AnswerPRSelection />
      <AnswerLoading />
      {chat.isError && <AnswerError />}
    </>
  );
};

/** Compound Component 조립 */
Answer.Loading = AnswerLoading;
Answer.PRSelection = AnswerPRSelection;
Answer.Error = AnswerError;
Answer.FilterBar = AnswerFilterBar;
Answer.Content = AnswerContent;
Answer.Actions = AnswerActions;
Answer.Feedback = AnswerFeedback;
Answer.Full = AnswerFull;

export default Answer;
