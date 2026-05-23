// block 콘텐츠 — blocks[] 를 block_type 별로 분기 렌더.
// code → CodeBlock, bullets → 불릿 리스트, 그 외(text/default) → OriginalMarkdown.

import CodeBlock from '@/features/hybrid-search/components/original/CodeBlock';
import OriginalMarkdown from '@/features/hybrid-search/components/original/OriginalMarkdown';
import type {
  OriginalBlock,
  OriginalBlockPayload,
} from '@/features/hybrid-search/types/originalApi';

interface BlockContentProps {
  content: OriginalBlockPayload;
}

// 연속한 bullets 블록을 하나의 리스트로 묶기 위한 렌더 단위.
type BlockGroup =
  | { kind: 'bullets'; items: string[] }
  | { kind: 'single'; block: OriginalBlock };

// bullets 가 연달아 오면 한 <ul> 로 합치고, 나머지는 개별 블록으로 둔다.
function groupBlocks(blocks: OriginalBlock[]): BlockGroup[] {
  const groups: BlockGroup[] = [];

  for (const block of blocks) {
    if (block.block_type === 'bullets') {
      const text = block.text ?? block.markdown ?? block.value ?? '';
      const last = groups.at(-1);
      if (last?.kind === 'bullets') {
        last.items.push(text);
      } else {
        groups.push({ kind: 'bullets', items: [text] });
      }
      continue;
    }
    groups.push({ kind: 'single', block });
  }

  return groups;
}

function SingleBlock({ block }: { block: OriginalBlock }) {
  if (block.block_type === 'code') {
    return <CodeBlock code={block.value ?? block.text ?? ''} />;
  }
  return <OriginalMarkdown text={block.markdown ?? block.value ?? block.text ?? ''} />;
}

export default function BlockContent({ content }: BlockContentProps) {
  const groups = groupBlocks(content.blocks);

  return (
    <div className="flex w-full flex-col gap-2">
      {groups.map((group, index) => {
        if (group.kind === 'bullets') {
          return (
            <ul
              key={`bullets-${index}`}
              className="text-body-small text-content-normal flex flex-col gap-2 pl-5"
            >
              {group.items.map((item, itemIndex) => (
                <li key={`bullet-${index}-${itemIndex}`} className="list-disc break-words">
                  {item}
                </li>
              ))}
            </ul>
          );
        }
        return <SingleBlock key={`block-${index}`} block={group.block} />;
      })}
    </div>
  );
}
