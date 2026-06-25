import type { SlackFileRaw } from '@/features/hybrid-search/types/slackOriginalApi';
import { formatFileSize } from '@/features/hybrid-search/utils/format/formatFileSize';
import { formatFileType } from '@/features/hybrid-search/utils/format/formatFileType';
import FileIcon from '@/public/icons/icon/file_filled.svg';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface SlackFileAttachmentProps {
  file: SlackFileRaw;
  originalUrl?: string | null;
}

export default function SlackFileAttachment({ file, originalUrl }: SlackFileAttachmentProps) {
  const name = file.title || file.name || '이름 없음';
  const meta = [formatFileSize(file.size), formatFileType(name, file.mimetype)].filter(Boolean).join(' · ');
  const href = originalUrl && isSafeUrl(originalUrl) ? originalUrl : null;
  const content = (
    <span className="bg-fill-normal-strong border-line-normal-neutral flex w-full items-center gap-2.5 rounded-lg border p-2 text-left">
      <span className="bg-fill-normal-normal flex shrink-0 items-center justify-center rounded-lg p-2">
        <FileIcon className="text-icon-primary-assistive size-7" aria-hidden />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-body-small text-text-normal-neutral max-w-62.5 truncate font-medium">{name}</span>
        {meta && <span className="text-body-xsmall text-text-normal-assistive truncate font-medium">{meta}</span>}
      </span>
    </span>
  );

  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block w-full">
      {content}
    </a>
  ) : (
    content
  );
}
