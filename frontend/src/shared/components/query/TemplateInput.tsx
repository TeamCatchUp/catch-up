'use client';

import { RefObject, useCallback, useEffect, useRef, useState } from 'react';

import IconDelete from '@/public/icons/icon/delete (2).svg';
import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { TipData } from '@/shared/types/template';
import { cn } from '@/shared/utils/cn';

interface TemplateInputProps {
  tip: TipData;
  input: UseSearchInputReturn;
  submitButtonRef?: RefObject<HTMLButtonElement | null>;
}

interface InlineFieldInputProps {
  fieldKey: string;
  placeholder: string;
  value: string;
  hasError: boolean;
  autoFocus?: boolean;
  onChange: (key: string, val: string) => void;
  onFocus?: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLElement>) => void;
  inputRef: (el: HTMLElement | null) => void;
}

const FIELD_MAX_LENGTH = 40;

const InlineFieldInput = ({
  fieldKey,
  placeholder,
  value,
  hasError,
  autoFocus,
  onChange,
  onFocus,
  onKeyDown,
  inputRef,
}: InlineFieldInputProps) => {
  const spanRef = useRef<HTMLSpanElement | null>(null);
  const measureRef = useRef<HTMLSpanElement>(null);
  const [minWidth, setMinWidth] = useState(0);
  const [contentWidth, setContentWidth] = useState(0);

  // 입력 폭 > placeholder 폭이면 inline(줄바꿈 가능), 아니면 inline-block(min-width 적용)
  const useInlineMode = value && contentWidth > minWidth;

  // callback ref: 동기적으로 부모에 ref 전달 + 내부 ref 보관
  const setSpanRef = useCallback(
    (el: HTMLSpanElement | null) => {
      spanRef.current = el;
      inputRef(el);
    },
    [inputRef],
  );

  // placeholder 텍스트 폭 측정 → min-width
  useEffect(() => {
    if (measureRef.current) {
      setMinWidth(measureRef.current.scrollWidth);
    }
  }, [placeholder]);

  // autoFocus 처리
  useEffect(() => {
    if (autoFocus && spanRef.current) {
      spanRef.current.focus();
    }
  }, [autoFocus]);

  const handleInput = useCallback(
    (e: React.FormEvent<HTMLSpanElement>) => {
      let text = e.currentTarget.textContent ?? '';
      if (text.length > FIELD_MAX_LENGTH) {
        text = text.slice(0, FIELD_MAX_LENGTH);
        e.currentTarget.textContent = text;
        // 커서를 끝으로 이동
        const sel = window.getSelection();
        if (sel && e.currentTarget.lastChild) {
          sel.collapse(e.currentTarget.lastChild, e.currentTarget.lastChild.textContent?.length ?? 0);
        }
      }
      // 입력 폭 측정 (하이브리드 전환 기준)
      setContentWidth(e.currentTarget.scrollWidth);
      onChange(fieldKey, text);
    },
    [fieldKey, onChange],
  );

  const handleClear = useCallback(() => {
    if (spanRef.current) {
      spanRef.current.textContent = '';
    }
    setContentWidth(0);
    onChange(fieldKey, '');
    spanRef.current?.focus();
  }, [fieldKey, onChange]);

  return (
    <span
      className={cn(
        'inline cursor-text rounded-lg border bg-fill-primary-assistive px-2 py-1',
        hasError ? 'border-edge-error' : 'border-edge-neutral',
      )}
      style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}
      onClick={() => spanRef.current?.focus()}
    >
      {/* 숨겨진 측정 span: placeholder 폭 기준 min-width 계산 */}
      <span
        ref={measureRef}
        className="pointer-events-none invisible absolute whitespace-pre text-body-medium select-none"
        aria-hidden="true"
      >
        {placeholder}
      </span>
      <span
        ref={setSpanRef}
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onFocus={onFocus}
        onKeyDown={onKeyDown}
        className={cn(
          'cursor-text align-baseline text-body-medium text-content-primary outline-none',
          useInlineMode ? 'inline' : 'inline-block',
        )}
        style={{ minWidth: !useInlineMode && value && minWidth > 0 ? `${minWidth}px` : undefined }}
      />
      {!value && (
        <span className="pointer-events-none select-none text-content-assistive">{placeholder}</span>
      )}
      {value && (
        <button
          type="button"
          tabIndex={-1}
          onClick={(e) => {
            e.stopPropagation();
            handleClear();
          }}
          className="ml-1 inline-flex h-5 w-5 cursor-pointer items-center justify-center align-middle"
        >
          <IconDelete className="h-5 w-5 text-icon-assistive" />
        </button>
      )}
    </span>
  );
};

export default function TemplateInput({ tip, input, submitButtonRef }: TemplateInputProps) {
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});
  // template 렌더링 순서로 field key 추출 (Tab 이동이 시각적 순서를 따르도록)
  const fieldKeys = tip.template
    .filter((seg): seg is { field: string } => typeof seg !== 'string')
    .map((seg) => seg.field);

  const setFieldRef = useCallback(
    (key: string) => (el: HTMLElement | null) => {
      fieldRefs.current[key] = el;
    },
    [],
  );

  // 에러 발생 시 첫 번째 에러 필드에 포커스
  useEffect(() => {
    const firstError = fieldKeys.find((key) => input.templateFieldErrors[key]);
    if (firstError) {
      fieldRefs.current[firstError]?.focus();
    }
  }, [input.templateFieldErrors, fieldKeys]);

  const handleFieldKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLElement>) => {
      // Shift+Enter 무시
      if (e.key === 'Enter' && e.shiftKey) {
        e.preventDefault();
        return;
      }
      // Enter → submit
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        input.handleSubmit();
        return;
      }
      // Tab 이동
      if (e.key === 'Tab') {
        const currentKey = (e.target as HTMLElement).getAttribute('data-field-key');
        const currentIdx = fieldKeys.indexOf(currentKey ?? '');

        if (e.shiftKey) {
          // Shift+Tab → 이전 필드
          if (currentIdx > 0) {
            e.preventDefault();
            fieldRefs.current[fieldKeys[currentIdx - 1]]?.focus();
          }
        } else {
          // Tab → 다음 필드 또는 submit 버튼
          if (currentIdx < fieldKeys.length - 1) {
            e.preventDefault();
            fieldRefs.current[fieldKeys[currentIdx + 1]]?.focus();
          } else if (submitButtonRef?.current) {
            e.preventDefault();
            submitButtonRef.current.focus();
          }
        }
      }
    },
    [fieldKeys, input, submitButtonRef],
  );

  const handleTextKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLSpanElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (!e.shiftKey) input.handleSubmit();
      }
    },
    [input],
  );

  return (
    <div className="text-body-medium min-h-10 cursor-text leading-[1.7]" onClick={() => input.setIsFocused(true)}>
      {tip.template.map((segment, index) => {
        if (typeof segment === 'string') {
          return (
            <span
              key={index}
              contentEditable
              suppressContentEditableWarning
              onFocus={() => input.setIsFocused(true)}
              onInput={(e) => input.setTemplateTextOverride(index, e.currentTarget.textContent ?? '')}
              onKeyDown={handleTextKeyDown}
              className="cursor-text text-content-neutral outline-none"
            >
              {segment}
            </span>
          );
        }

        const field = tip.fields.find((f) => f.key === segment.field);
        if (!field) return null;

        const isFirstField = fieldKeys[0] === field.key;

        return (
          <InlineFieldInput
            key={field.key}
            fieldKey={field.key}
            placeholder={field.placeholder}
            value={input.templateFieldValues[field.key] ?? ''}
            hasError={!!input.templateFieldErrors[field.key]}
            autoFocus={isFirstField}
            onChange={input.setTemplateFieldValue}
            onFocus={() => input.setIsFocused(true)}
            onKeyDown={handleFieldKeyDown}
            inputRef={(el) => {
              setFieldRef(field.key)(el);
              if (el) el.setAttribute('data-field-key', field.key);
            }}
          />
        );
      })}
    </div>
  );
}
