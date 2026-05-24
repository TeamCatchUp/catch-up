// file 콘텐츠 — files[] 각 요소를 FileRow 로 렌더.
// connector/documentId 는 FileRow 가 다운로드 mutation 호출 시 사용.

import FileRow from '@/features/hybrid-search/components/original/FileRow';
import type { OriginalFilePayload } from '@/features/hybrid-search/types/originalApi';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

interface FileContentProps {
  content: OriginalFilePayload;
  connector: SourceTypeApi;
  documentId: string;
}

export default function FileContent({ content, connector, documentId }: FileContentProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      {content.files.map((file, index) => (
        <FileRow
          key={file.file_key ?? index}
          file={file}
          connector={connector}
          documentId={documentId}
        />
      ))}
    </div>
  );
}
