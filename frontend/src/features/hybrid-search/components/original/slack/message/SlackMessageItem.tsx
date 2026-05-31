import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';
import { cn } from '@/shared/utils/cn';

import SlackMessageAvatar from './SlackMessageAvatar';
import SlackMessageBody from './SlackMessageBody';

interface SlackMessageItemProps {
  message: SlackMessageView;
}

export default function SlackMessageItem({ message }: SlackMessageItemProps) {
  const isBot = message.author.kind === 'bot';

  return (
    <article className="flex w-99.75 max-w-full items-start pl-3 pr-2.5">
      <div className="flex min-w-0 flex-1 items-start gap-3 overflow-hidden py-1">
        <SlackMessageAvatar
          name={message.author.name}
          avatarUrl={message.author.avatarUrl}
          kind={message.author.kind}
        />
        <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
          <div className="flex h-8 w-full items-center gap-1.5">
            <span
              className={cn(
                'text-heading-small min-w-0 flex-1 truncate font-semibold',
                isBot ? 'text-content-primary' : 'text-content-alternative',
              )}
            >
              {message.author.name}
            </span>
            {message.timeLabel && (
              <span className="text-body-xsmall text-content-assistive shrink-0 font-medium">{message.timeLabel}</span>
            )}
            {message.editedLabel && (
              <>
                <span aria-hidden className="bg-edge-neutral h-2.5 w-px shrink-0" />
                <span className="text-body-xsmall text-content-assistive shrink-0 font-medium">
                  {message.editedLabel}
                </span>
              </>
            )}
          </div>
          <SlackMessageBody message={message} />
        </div>
      </div>
    </article>
  );
}
