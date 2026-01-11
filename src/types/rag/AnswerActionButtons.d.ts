interface IconItem {
  name: string;
  icon: React.FC<React.SVGProps<SVGElement>>;
}

interface AnswerActionButtonsProps {
  icons: IconItem[];
  messageIdx: number;
  feedbackVisibleMap: { [key: number]: boolean };
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<{ [key: number]: boolean }>>;
}

interface ErrorResponseProps {
  icons: IconItem[];
  messageIdx: number;
  feedbackVisibleMap: { [key: number]: boolean };
  setFeedbackVisibleMap: React.Dispatch<React.SetStateAction<{ [key: number]: boolean }>>;
}
