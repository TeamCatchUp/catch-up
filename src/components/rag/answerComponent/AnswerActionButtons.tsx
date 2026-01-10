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

const AnswerActionButtons = ({
  icons,
  messageIdx,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
}: AnswerActionButtonsProps) => {
  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        // const activeClass = isThumbsDown && showFeedback ? 'bg-neutral-3 border-neutral-5' : '';
        // return (
        //   <button
        //     key={i}
        //     onClick={() => {
        //       if (isThumbsDown) {
        //         setFeedbackVisibleMap((prev) => ({
        //           ...prev,
        //           [idx]: !prev[idx],
        //         }));
        //       }
        //     }}
        //     className={`icon-button-only-gray cursor-pointer p-1.5 ${activeClass}`}
        //   >
        //     <item.icon className="h-6 w-6 text-gray-50" />
        //   </button>
        // );
        const isActive = isThumbsDown && feedbackVisibleMap[messageIdx];

        return (
          <button
            key={i}
            onClick={() => {
              if (isThumbsDown) {
                setFeedbackVisibleMap((prev) => ({
                  ...prev,
                  [messageIdx]: !prev[messageIdx],
                }));
              }
            }}
            className={`icon-button-only-gray cursor-pointer p-1.5 ${isActive ? 'bg-neutral-3 border-neutral-5' : ''}`}
          >
            <item.icon className="h-6 w-6 text-gray-50" />
          </button>
        );
      })}
    </div>
  );
};

export default AnswerActionButtons;
