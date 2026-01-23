interface IconItem {
  name: string;
  icon: React.FC<React.SVGProps<SVGElement>>;
}

interface AnswerActionButtonsProps {
  icons: IconItem[];
  messageId: string;
  // feedbackVisibleMap: { [key: number]: boolean };
  // setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<{ [key: number]: boolean }>>;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}

interface ErrorResponseProps {
  icons: IconItem[];
  messageId: string;
  // feedbackVisibleMap: { [key: number]: boolean };
  // setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<{ [key: number]: boolean }>>;
  // feedbackSubmittedMap: { [key: string]: boolean };
  // setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  feedbackSubmittedMap: Record<string, boolean>;
  setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}

interface FeedbackSectionProps {
  messageId: string;
  // feedbackVisibleMap: { [key: string]: boolean };
  // setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  // feedbackSubmittedMap: { [key: string]: boolean };
  // setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  feedbackVisibleMap: Record<string, boolean>;
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  feedbackSubmittedMap: Record<string, boolean>;
  setFeedbackSubmittedMap: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
}
