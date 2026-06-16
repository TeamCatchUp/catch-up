'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $getNodeByKey } from 'lexical';
import { toast } from 'sonner';

import IconDelete from '@/public/icons/icon/delete_circle.svg';
import IconError from '@/public/icons/icon/error.svg';
import { cn } from '@/shared/utils/cn';

// ─── Context ────────────────────────────────────────────────
export interface TemplateFieldContextValue {
  fieldValues: Record<string, string>;
  fieldErrors: Record<string, boolean>;
  setFieldValue: (key: string, val: string) => void;
  onSubmit: () => void;
  onFocus: () => void;
  /** 필드 순서 (Tab 이동용) */
  fieldKeys: string[];
  /** 필드 ref 등록/해제 */
  registerFieldRef: (key: string, el: HTMLElement | null) => void;
  /** 특정 필드로 포커스 이동 */
  focusField: (key: string) => void;
  /** submit 버튼으로 포커스 이동 */
  focusSubmitButton: () => void;
}

export const TemplateFieldContext = createContext<TemplateFieldContextValue | null>(null);

// ─── Constants ──────────────────────────────────────────────
export const FIELD_MAX_LENGTH = 40;

function showMaxLengthToast() {
  toast(
    <span className="flex items-center gap-2">
      <IconError className="h-6 w-6 shrink-0" />
      최대 40자까지 입력할 수 있어요.
    </span>,
    { id: 'field-max-length' },
  );
}

// ─── Component ──────────────────────────────────────────────
interface FieldChipComponentProps {
  fieldKey: string;
  placeholder: string;
  nodeKey: string;
}

export default function FieldChipComponent({ fieldKey, placeholder, nodeKey }: FieldChipComponentProps) {
  const ctx = useContext(TemplateFieldContext);
  const [editor] = useLexicalComposerContext();
  const spanRef = useRef<HTMLSpanElement | null>(null);
  const measureRef = useRef<HTMLSpanElement>(null);
  const isComposingRef = useRef(false);
  const [minWidth, setMinWidth] = useState(0);
  const [contentWidth, setContentWidth] = useState(0);

  if (!ctx) throw new Error('FieldChipComponent must be used within TemplateFieldContext.Provider');

  const value = ctx.fieldValues[fieldKey] ?? '';
  const hasError = !!ctx.fieldErrors[fieldKey];
  const isAtMaxLength = value.length >= FIELD_MAX_LENGTH;
  const useInlineMode = value && contentWidth > minWidth;

  // placeholder 폭 측정 → min-width
  useEffect(() => {
    if (measureRef.current) {
      setMinWidth(measureRef.current.scrollWidth);
    }
  }, [placeholder]);

  // 첫 번째 필드 autoFocus
  useEffect(() => {
    if (ctx.fieldKeys[0] === fieldKey && spanRef.current) {
      spanRef.current.focus();
    }
  }, [ctx.fieldKeys, fieldKey]);

  // fieldRefs에 등록
  useEffect(() => {
    ctx.registerFieldRef(fieldKey, spanRef.current);
    return () => {
      ctx.registerFieldRef(fieldKey, null);
    };
  }, [ctx, fieldKey]);

  const handleInput = useCallback(
    (e: React.FormEvent<HTMLSpanElement>) => {
      let text = e.currentTarget.textContent ?? '';
      if (text.length > FIELD_MAX_LENGTH) {
        text = text.slice(0, FIELD_MAX_LENGTH);
        e.currentTarget.textContent = text;
        const sel = window.getSelection();
        if (sel && e.currentTarget.lastChild) {
          sel.collapse(e.currentTarget.lastChild, e.currentTarget.lastChild.textContent?.length ?? 0);
        }
        showMaxLengthToast();
      }
      setContentWidth(e.currentTarget.scrollWidth);
      ctx.setFieldValue(fieldKey, text);
    },
    [fieldKey, ctx],
  );

  const handleClear = useCallback(() => {
    if (spanRef.current) {
      spanRef.current.textContent = '';
    }
    setContentWidth(0);
    ctx.setFieldValue(fieldKey, '');
    spanRef.current?.focus();
  }, [fieldKey, ctx]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLSpanElement>) => {
      // Shift+Enter 무시
      if (e.key === 'Enter' && e.shiftKey) {
        e.preventDefault();
        return;
      }
      // Enter → submit (IME 조합 중에는 무시)
      if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
        e.preventDefault();
        ctx.onSubmit();
        return;
      }
      // Backspace on empty → 칩 삭제
      if (e.key === 'Backspace' && !value) {
        e.preventDefault();
        editor.update(() => {
          const node = $getNodeByKey(nodeKey);
          if (node) node.remove();
        });
        return;
      }
      // Tab 이동
      if (e.key === 'Tab') {
        e.preventDefault();

        // IME 조합 중이면 현재 텍스트 확정
        if (isComposingRef.current && spanRef.current) {
          const text = (spanRef.current.textContent ?? '').slice(0, FIELD_MAX_LENGTH);
          ctx.setFieldValue(fieldKey, text);
          isComposingRef.current = false;
        }

        const currentIdx = ctx.fieldKeys.indexOf(fieldKey);
        const shiftKey = e.shiftKey;
        requestAnimationFrame(() => {
          if (shiftKey) {
            if (currentIdx > 0) ctx.focusField(ctx.fieldKeys[currentIdx - 1]);
          } else {
            if (currentIdx < ctx.fieldKeys.length - 1) ctx.focusField(ctx.fieldKeys[currentIdx + 1]);
            else ctx.focusSubmitButton();
          }
        });
      }
    },
    [value, fieldKey, ctx, editor, nodeKey],
  );

  return (
    <span
      className={cn(
        'bg-fill-primary-normal-assistive inline cursor-text rounded-lg border px-2 py-1',
        hasError
          ? 'border-status-destructive'
          : isAtMaxLength
            ? 'border-status-destructive'
            : 'border-line-normal-neutral',
      )}
      style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}
      onClick={() => spanRef.current?.focus()}
    >
      {/* 숨겨진 측정 span: placeholder 폭 기준 min-width 계산 */}
      <span
        ref={measureRef}
        className="text-body-medium pointer-events-none invisible absolute whitespace-pre select-none"
        aria-hidden="true"
      >
        {placeholder}
      </span>
      <span
        ref={spanRef}
        contentEditable
        suppressContentEditableWarning
        onInput={handleInput}
        onFocus={ctx.onFocus}
        onKeyDown={handleKeyDown}
        onCompositionStart={() => {
          isComposingRef.current = true;
        }}
        onCompositionEnd={(e) => {
          isComposingRef.current = false;
          const raw = e.currentTarget.textContent ?? '';
          const text = raw.slice(0, FIELD_MAX_LENGTH);
          if (raw.length > FIELD_MAX_LENGTH) showMaxLengthToast();
          setContentWidth(e.currentTarget.scrollWidth);
          ctx.setFieldValue(fieldKey, text);
        }}
        className={cn(
          'text-body-medium text-text-primary-normal cursor-text align-baseline outline-none',
          useInlineMode ? 'inline' : 'inline-block',
        )}
        style={{ minWidth: !useInlineMode ? (value && minWidth > 0 ? minWidth : 1) : undefined }}
      />
      {!value && <span className="text-text-normal-assistive pointer-events-none select-none">{placeholder}</span>}
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
          <IconDelete className="text-icon-normal-assistive h-5 w-5" />
        </button>
      )}
    </span>
  );
}
