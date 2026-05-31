import Image from 'next/image';

import type { SlackAttachmentRaw } from '@/features/hybrid-search/types/slackOriginalApi';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface SlackLinkPreviewProps {
  attachment: SlackAttachmentRaw;
}

export default function SlackLinkPreview({ attachment }: SlackLinkPreviewProps) {
  const href = attachment.title_link && isSafeUrl(attachment.title_link) ? attachment.title_link : null;
  const rawImageUrl = attachment.image_url || attachment.thumb_url;
  const imageUrl = rawImageUrl && isSafeUrl(rawImageUrl) ? rawImageUrl : null;
  if (!imageUrl && !attachment.title && !attachment.text && !href) return null;

  return (
    <div className="bg-fill-normal-assistive-dark border-edge-neutral flex w-70 flex-col items-start justify-center overflow-hidden rounded-xl border">
      {imageUrl && (
        <Image src={imageUrl} alt="" width={280} height={120} className="h-30 w-full object-cover" unoptimized />
      )}
      <div className="flex w-full flex-col items-start gap-1 px-4 py-5">
        {attachment.title && (
          <p className="text-heading-small text-content-neutral max-w-62.5 truncate font-semibold">
            {attachment.title}
          </p>
        )}
        {attachment.text && (
          <p className="text-body-small text-content-neutral w-full truncate font-medium">{attachment.text}</p>
        )}
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-body-xsmall text-content-primary w-full truncate underline"
          >
            링크 {href}
          </a>
        )}
      </div>
    </div>
  );
}
