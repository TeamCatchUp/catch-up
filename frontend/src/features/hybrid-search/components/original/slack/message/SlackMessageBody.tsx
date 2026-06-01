import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';

import SlackFileAttachment from '../attachments/SlackFileAttachment';
import SlackLinkPreview from '../attachments/SlackLinkPreview';
import SlackRichTextRenderer from '../rich-text/SlackRichTextRenderer';

interface SlackMessageBodyProps {
  message: SlackMessageView;
  originalUrl?: string | null;
}

export default function SlackMessageBody({ message, originalUrl }: SlackMessageBodyProps) {
  return (
    <div className="flex w-full flex-col items-start gap-3">
      <SlackRichTextRenderer blocks={message.blocks} />
      {message.files.map((file) => (
        <SlackFileAttachment key={file.id || file.name} file={file} originalUrl={originalUrl} />
      ))}
      {message.attachments.map((attachment, index) => (
        <SlackLinkPreview key={`${attachment.id ?? index}`} attachment={attachment} />
      ))}
    </div>
  );
}
