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
  onFeedbackSubmitted?: (messageId: string) => void;
}

interface FeedbackSectionProps {
  messageId: string;
  chatHistoryId?: string;
  hasFeedback?: boolean;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  onFeedbackSubmitted?: (messageId: string) => void;
}
