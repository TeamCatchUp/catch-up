// content_type 별 콘텐츠 컴포넌트 디스패처. 한 메시지의 contents[] 각 요소를 받는다.
// file 분기만 connector/documentId 사용 — 나머지는 무시. 시그니처 통일을 위해 모두 받음.

import BlockContent from '@/features/hybrid-search/components/original/channel-talk/contents/BlockContent';
import ButtonContent from '@/features/hybrid-search/components/original/channel-talk/contents/ButtonContent';
import FileContent from '@/features/hybrid-search/components/original/channel-talk/contents/FileContent';
import FormContent from '@/features/hybrid-search/components/original/channel-talk/contents/FormContent';
import TextContent from '@/features/hybrid-search/components/original/channel-talk/contents/TextContent';
import type { OriginalContent } from '@/features/hybrid-search/types/originalApi';
import type { SourceTypeApi } from '@/shared/types/sourceApi';

interface ContentRendererProps {
  content: OriginalContent;
  connector: SourceTypeApi;
  documentId: string;
}

export default function ContentRenderer({ content, connector, documentId }: ContentRendererProps) {
  switch (content.content_type) {
    case 'text':
      return <TextContent content={content.payload} />;
    case 'block':
      return <BlockContent content={content.payload} />;
    case 'button':
      return <ButtonContent content={content.payload} />;
    case 'form':
      return <FormContent content={content.payload} />;
    case 'file':
      return <FileContent content={content.payload} connector={connector} documentId={documentId} />;
    default: {
      // content_type 이 늘어나면 컴파일 단계에서 누락을 잡는다.
      const _exhaustive: never = content;
      return _exhaustive;
    }
  }
}
