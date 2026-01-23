import Error from '/public/icons/icon/error.svg';
import AnswerActionButtons from '@/components/rag/answerComponent/AnswerActionButtons';
import FeedbackSection from '@/components/rag/answerComponent/FeedbackSection';

const ErrorResponse = ({
  icons,
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
  feedbackSubmittedMap,
  setFeedbackSubmittedMap,
}: ErrorResponseProps) => {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-8">
        <div className="bg-neutral-1 flex items-center gap-4 rounded-2xl px-5 py-3">
          <Error className="h-6 w-6 text-gray-50" />
          <div className="text-label-small text-gray-70 whitespace-pre-line">{`일시적인 오류로 답변을 생성하지 못했습니다.\n잠시 후 다시 시도해주세요.`}</div>
        </div>
        <AnswerActionButtons
          icons={icons}
          messageId={messageId}
          feedbackVisibleMap={feedbackVisibleMap}
          setFeedbackVisibleMap={setFeedbackVisibleMap}
        />
      </div>
      <FeedbackSection
        messageId={messageId}
        feedbackVisibleMap={feedbackVisibleMap}
        setFeedbackVisibleMap={setFeedbackVisibleMap}
        feedbackSubmittedMap={feedbackSubmittedMap}
        setFeedbackSubmittedMap={setFeedbackSubmittedMap}
      />
    </div>
  );
};

export default ErrorResponse;
