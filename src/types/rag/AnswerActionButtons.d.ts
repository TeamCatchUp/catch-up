interface IconItem {
  name: string;
  icon: React.FC<React.SVGProps<SVGElement>>;
}

interface AnswerActionButtonsProps {
  icons: IconItem[];
  messageId: string;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}

interface ErrorResponseProps {
  icons: IconItem[];
  messageId: string;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  hasFeedback?: boolean;
  // feedbackSubmittedMap: Record<string, boolean>;
  // setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}

interface FeedbackSectionProps {
  messageId: string;
  chatHistoryId?: string;
  hasFeedback?: boolean;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  // feedbackSubmittedMap: Record<string, boolean>;
  // setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}
