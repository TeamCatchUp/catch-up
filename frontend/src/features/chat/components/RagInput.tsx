'use client';

import { useRef, useState } from 'react';

import type { UseRagFiltersReturn } from '@/features/chat/hooks/filter/useRagFilters';
import ArrowSend from '@/public/icons/icon/arrow_send.svg';
import CancelSmall from '@/public/icons/icon/cancel_small.svg';
import SearchFile from '@/public/icons/icon/search_file.svg';
import Stop from '@/public/icons/icon/stop.svg';
import SourceChipsRow from '@/shared/components/SourceChipsRow';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

const INITIAL_TEXTAREA_HEIGHT_PX = 26;
const MAX_TEXTAREA_HEIGHT_PX = 270;

interface RagInputProps {
  filters: UseRagFiltersReturn;
  isLoading: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
  onNewMessage: () => void;
}

export default function RagInput({ filters, isLoading, onSendMessage, onStop, onNewMessage }: RagInputProps) {
  const [newInput, setNewInput] = useState('');
  const textAreaRef = useRef<HTMLTextAreaElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewInput(e.target.value);

    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, MAX_TEXTAREA_HEIGHT_PX);
    e.target.style.height = `${newHeight}px`;
  };

  const handleSendMessage = async () => {
    if (!newInput.trim() || isLoading) return;

    const message = newInput;
    setNewInput('');

    if (textAreaRef.current) {
      textAreaRef.current.style.height = `${INITIAL_TEXTAREA_HEIGHT_PX}px`;
    }

    onNewMessage();
    await onSendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="px-16 pb-2.5 backdrop-blur-[10px]">
      <div className="mx-auto flex w-full max-w-203 flex-col items-center gap-2">
        <div className="border-line-normal-normal bg-fill-normal-normal flex w-full flex-col rounded-2xl border p-4">
          <div
            className={cn(
              'overflow-hidden transition-all duration-300 ease-in-out',
              filters.isFilterOpen ? 'mb-3 max-h-40 opacity-100' : 'max-h-0 opacity-0',
            )}
          >
            <div className="flex items-center gap-1.5">
              <Button
                variant="icon-outline-gray"
                size="md"
                type="button"
                onClick={filters.toggleFilter}
                aria-label="상세 검색 닫기"
              >
                <CancelSmall className="h-6 w-6" />
              </Button>
              <SourceChipsRow
                selectedSources={filters.selectedSources}
                onToggle={filters.setSelectedSources}
                className="justify-start"
              />
            </div>
          </div>

          <textarea
            ref={textAreaRef}
            placeholder="답은 이미 사내에 있어요. 바로 찾아드릴게요."
            value={newInput}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            className="text-body-medium text-text-normal-normal placeholder:text-text-normal-assistive h-6.5 max-h-67.5 w-full resize-none overflow-y-auto outline-none"
          />

          <div className="mt-3 flex h-8 items-center justify-between">
            <button
              type="button"
              onClick={filters.toggleFilter}
              aria-expanded={filters.isFilterOpen}
              className={cn(
                'text-text-normal-neutral flex h-7 cursor-pointer items-center gap-1 rounded-full px-1.5 py-1',
                filters.isFilterOpen && 'bg-fill-normal-interaction-pressed',
              )}
            >
              <SearchFile className="h-5 w-5 shrink-0" />
              <span className="text-body-xsmall">상세 검색</span>
            </button>

            {isLoading ? (
              <button
                type="button"
                aria-label="답변 생성 중지"
                onClick={onStop}
                className="bg-fill-normal-interaction-disable flex h-10 w-10 items-center justify-center rounded-full"
              >
                <Stop className="text-text-normal-neutral relative left-px h-6 w-6 cursor-pointer" />
              </button>
            ) : (
              <button
                type="button"
                aria-label="질문 보내기"
                onClick={handleSendMessage}
                disabled={isLoading || !newInput.trim()}
                className={cn(
                  'cursor-pointer rounded-full p-2 transition-colors',
                  newInput.trim()
                    ? 'bg-fill-primary-normal-normal'
                    : 'bg-fill-normal-interaction-inactive border-line-normal-assistive border',
                )}
              >
                <ArrowSend
                  className={cn(
                    'h-6 w-6 cursor-pointer',
                    newInput.trim() ? 'text-white' : 'text-text-normal-assistive',
                  )}
                />
              </button>
            )}
          </div>
        </div>

        <p className="text-label-xsmall text-text-normal-alternative">
          출처를 기반으로 정보를 제공합니다. 자세한 내용은 원문을 확인해주세요.
        </p>
      </div>
    </div>
  );
}
