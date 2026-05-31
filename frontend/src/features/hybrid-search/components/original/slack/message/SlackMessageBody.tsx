import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';

import SlackFileAttachment from '../attachments/SlackFileAttachment';
import SlackImageGrid, { hasSafeSlackImagePreview } from '../attachments/SlackImageGrid';
import SlackLinkPreview from '../attachments/SlackLinkPreview';
import SlackRichTextRenderer from '../rich-text/SlackRichTextRenderer';

interface SlackMessageBodyProps {
  message: SlackMessageView;
}

export default function SlackMessageBody({ message }: SlackMessageBodyProps) {
  const imageFiles = message.files.filter(hasSafeSlackImagePreview);
  const fileRows = message.files.filter((file) => !hasSafeSlackImagePreview(file));

  return (
    <div className="flex w-full flex-col items-start gap-3">
      <SlackRichTextRenderer blocks={message.blocks} />
      {fileRows.map((file) => (
        <SlackFileAttachment key={file.id || file.name} file={file} />
      ))}
      {message.attachments.map((attachment, index) => (
        <SlackLinkPreview key={`${attachment.id ?? index}`} attachment={attachment} />
      ))}
      <SlackImageGrid files={imageFiles} />
    </div>
  );
}
