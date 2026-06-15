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
    token.style?.code &&
      'text-status-cautionary bg-fill-normal-strong border-line-normal-normal rounded-md border px-1.5 py-0.5',
  );
}

function renderTokens(tokens: SlackRichTextToken[]) {
  return tokens.map((token, index) => {
    if (token.type === 'mention') {
      return (
        <span
          key={index}
          className={cn(
            'bg-accent-light-blue-lighten text-text-primary-normal inline-flex rounded-md px-1.5 py-0.5 font-medium',
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
          className={cn('text-text-primary-normal wrap-break-word underline', tokenClassName(token))}
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
    <div className="text-body-small text-text-normal-normal flex w-full min-w-0 flex-col items-start gap-2 font-medium">
      {blocks.map((block, index) => {
        if (block.type === 'paragraph') {
          return (
            <p key={index} className="w-full min-w-0 wrap-break-word">
              {renderTokens(block.tokens)}
            </p>
          );
        }

        if (block.type === 'bullet_list') {
          return (
            <ul key={index} className="flex w-full min-w-0 list-disc flex-col gap-1 pl-5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="min-w-0 wrap-break-word">
                  {renderTokens(item)}
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === 'ordered_list') {
          return (
            <ol key={index} className="flex w-full min-w-0 list-decimal flex-col gap-1 pl-5" start={block.start}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="min-w-0 wrap-break-word">
                  {renderTokens(item)}
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === 'quote') {
          return (
            <blockquote
              key={index}
              className="border-line-normal-neutral flex w-full min-w-0 gap-4 border-l-4 pl-4 wrap-break-word"
            >
              {renderTokens(block.tokens)}
            </blockquote>
          );
        }

        return (
          <pre
            key={index}
            className="custom-scrollbar bg-fill-normal-strong border-line-normal-neutral text-text-normal-neutral max-h-62.5 w-full overflow-auto rounded-xl border px-4 py-3 font-[inherit] whitespace-pre-wrap"
          >
            {block.text}
          </pre>
        );
      })}
    </div>
  );
}
