import type { Dispatch, FC, SetStateAction, SVGProps } from 'react';

/**
 * 답변 액션 아이콘 정의 타입.
 * @interface IconItem
 */
export interface IconItem {
  name: string;
  icon: FC<SVGProps<SVGElement>>;
  activeIcon?: FC<SVGProps<SVGElement>>;
}

/**
 * 답변 액션 버튼 컴포넌트 props.
 * @interface AnswerActionButtonsProps
 */
export interface AnswerActionButtonsProps {
  icons: IconItem[];
  messageId: string;
  answerContent: string;
  hasFeedback?: boolean;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: Dispatch<SetStateAction<Record<string, boolean>>>;
}

/**
 * 오류 상태 답변 액션 컴포넌트 props.
 * @interface ErrorResponseProps
 */
export interface ErrorResponseProps {
  icons: IconItem[];
  messageId: string;
  sessionId: string;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: Dispatch<SetStateAction<Record<string, boolean>>>;
  hasFeedback?: boolean;
  onFeedbackSubmitted?: (messageId: string) => void;
}

/**
 * 피드백 섹션 컴포넌트 props.
 * @interface FeedbackSectionProps
 */
export interface FeedbackSectionProps {
  messageId: string;
  sessionId: string;
  chatHistoryId?: string;
  hasFeedback?: boolean;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: Dispatch<SetStateAction<Record<string, boolean>>>;
  onFeedbackSubmitted?: (messageId: string) => void;
}
