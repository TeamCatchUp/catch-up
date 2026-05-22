// file 콘텐츠 — files[] 각 요소를 FileRow 로 렌더.

import FileRow from '@/features/hybrid-search/components/original/FileRow';
import type { OriginalFilePayload } from '@/features/hybrid-search/types/originalApi';

interface FileContentProps {
  content: OriginalFilePayload;
}

export default function FileContent({ content }: FileContentProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      {content.files.map((file, index) => (
        <FileRow key={file.file_key ?? index} file={file} />
      ))}
    </div>
  );
}
