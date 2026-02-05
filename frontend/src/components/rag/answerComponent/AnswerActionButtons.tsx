import clsx from 'clsx';

const AnswerActionButtons = ({
  icons,
  messageId,
  feedbackVisibleMap,
  setFeedbackVisibleMap,
}: AnswerActionButtonsProps) => {
  return (
    <div className="flex gap-1">
      {icons.map((item, i) => {
        const isThumbsDown = item.name === 'ThumbsDown';
        const isActive = isThumbsDown && feedbackVisibleMap[messageId];

        return (
          <button
            key={i}
            onClick={() => {
              if (isThumbsDown) {
                setFeedbackVisibleMap((prev) => ({
                  ...prev,
                  [messageId]: !prev[messageId],
                }));
              }
            }}
            className={`icon-button-only-gray cursor-pointer p-1.5 ${isActive ? 'bg-neutral-3 border-neutral-5' : ''}`}
          >
            <item.icon className={clsx('h-6 w-6', isActive ? 'text-gray-70' : 'active:text-gray-70 text-gray-50')} />
          </button>
        );
      })}
    </div>
  );
};

export default AnswerActionButtons;
