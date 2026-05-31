import { useState } from 'react';

import type { SlackFileRaw } from '@/features/hybrid-search/types/slackOriginalApi';
import type { SlackMessageView } from '@/features/hybrid-search/types/slackOriginalModel';

import SlackFileAttachment from '../attachments/SlackFileAttachment';
import SlackImageGrid, { hasSafeSlackImagePreview } from '../attachments/SlackImageGrid';
import SlackLinkPreview from '../attachments/SlackLinkPreview';
import SlackRichTextRenderer from '../rich-text/SlackRichTextRenderer';

interface SlackMessageBodyProps {
  message: SlackMessageView;
}

function getFileKey(file: SlackFileRaw): string {
  return file.id || file.name || file.title || file.permalink || '';
}

export default function SlackMessageBody({ message }: SlackMessageBodyProps) {
  const [failedPreviewKeys, setFailedPreviewKeys] = useState<ReadonlySet<string>>(new Set());
  const imageFiles = message.files.filter(
    (file) => hasSafeSlackImagePreview(file) && !failedPreviewKeys.has(getFileKey(file)),
  );
  const fileRows = message.files.filter(
    (file) => !hasSafeSlackImagePreview(file) || failedPreviewKeys.has(getFileKey(file)),
  );

  const handlePreviewError = (file: SlackFileRaw) => {
    const key = getFileKey(file);
    if (!key) return;

    setFailedPreviewKeys((prev) => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  };

  return (
    <div className="flex w-full flex-col items-start gap-3">
      <SlackRichTextRenderer blocks={message.blocks} />
      {fileRows.map((file) => (
        <SlackFileAttachment key={file.id || file.name} file={file} />
      ))}
      {message.attachments.map((attachment, index) => (
        <SlackLinkPreview key={`${attachment.id ?? index}`} attachment={attachment} />
      ))}
      <SlackImageGrid files={imageFiles} onPreviewError={handlePreviewError} />
    </div>
  );
}
