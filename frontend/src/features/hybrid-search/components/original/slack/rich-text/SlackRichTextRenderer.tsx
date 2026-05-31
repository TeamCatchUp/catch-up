import type { SlackBlockView, SlackRichTextToken } from '@/features/hybrid-search/types/slackOriginalModel';
import { cn } from '@/shared/utils/cn';
import { isSafeUrl } from '@/shared/utils/isSafeUrl';

interface SlackRichTextRendererProps {
  blocks: SlackBlockView[];
}

function tokenClassName(token: Extract<SlackRichTextToken, { type: 'text' | 'link' | 'mention' }>): string | undefined {
  return cn(
    token.style?.bold && 'font-bold',
    token.style?.italic && 'italic',
    token.style?.strike && 'line-through',
    token.style?.underline && 'underline',
    token.style?.code && 'text-status-cautionary bg-fill-strong border-edge-normal rounded-md border px-1.5 py-0.5',
  );
}

function renderTokens(tokens: SlackRichTextToken[]) {
  return tokens.map((token, index) => {
    if (token.type === 'mention') {
      return (
        <span
          key={index}
          className={cn(
            'bg-accent-light-blue-lighten text-content-primary inline-flex rounded-md px-1.5 py-0.5 font-medium',
            tokenClassName(token),
          )}
        >
          {token.label}
        </span>
      );
    }

    if (token.type === 'link') {
      if (!isSafeUrl(token.href)) {
        return (
          <span key={index} className={tokenClassName(token)}>
            {token.text}
          </span>
        );
      }

      return (
        <a
          key={index}
          href={token.href}
          target="_blank"
          rel="noopener noreferrer"
          className={cn('text-content-primary wrap-break-word underline', tokenClassName(token))}
        >
          {token.text}
        </a>
      );
    }

    if (token.type === 'emoji') return <span key={index}>{token.label}</span>;
    if (token.type === 'line_break') return <br key={index} />;

    return (
      <span key={index} className={tokenClassName(token)}>
        {token.text}
      </span>
    );
  });
}

export default function SlackRichTextRenderer({ blocks }: SlackRichTextRendererProps) {
  if (blocks.length === 0) return null;

  return (
    <div className="text-body-small text-content-normal flex w-full flex-col items-start gap-2 font-medium">
      {blocks.map((block, index) => {
        if (block.type === 'paragraph') {
          return (
            <p key={index} className="wrap-break-word">
              {renderTokens(block.tokens)}
            </p>
          );
        }

        if (block.type === 'bullet_list') {
          return (
            <ul key={index} className="list-disc space-y-1 pl-5 wrap-break-word">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderTokens(item)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === 'ordered_list') {
          return (
            <ol key={index} className="list-decimal space-y-1 pl-5 wrap-break-word" start={block.start}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderTokens(item)}</li>
              ))}
            </ol>
          );
        }

        if (block.type === 'quote') {
          return (
            <blockquote key={index} className="border-edge-neutral flex w-full gap-4 border-l-4 pl-4 wrap-break-word">
              {renderTokens(block.tokens)}
            </blockquote>
          );
        }

        return (
          <pre
            key={index}
            className="custom-scrollbar bg-fill-strong border-edge-neutral text-content-neutral max-h-62.5 w-full overflow-auto rounded-xl border px-4 py-3 font-[inherit] whitespace-pre-wrap"
          >
            {block.text}
          </pre>
        );
      })}
    </div>
  );
}
