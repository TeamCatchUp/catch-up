/**
 * useSearchInput
 * 검색 페이지의 입력 상태 관리 훅
 */

'use client';

import { RefObject, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { TipData } from '@/shared/types/template';

interface UseSearchInputOptions {
  inputRef: RefObject<HTMLTextAreaElement | null>;
  selectedSources?: string[];
  tipData?: TipData[];
}

export interface UseSearchInputReturn {
  value: string;
  setValue: (v: string) => void;
  hasText: boolean;
  isMultiLine: boolean;
  isFocused: boolean;
  setIsFocused: (f: boolean) => void;
  isFromTemplate: boolean;
  setIsFromTemplate: (v: boolean) => void;
  selectedTipIndex: number | null;
  setSelectedTipIndex: (idx: number | null) => void;
  templateFieldValues: Record<string, string>;
  setTemplateFieldValue: (key: string, val: string) => void;
  templateFieldErrors: Record<string, boolean>;
  setTemplateFieldErrors: (errors: Record<string, boolean>) => void;
  resetTemplateFields: () => void;
  handleSubmit: (queryOverride?: string) => void;
}

export const useSearchInput = ({
  inputRef,
  selectedSources,
  tipData,
}: UseSearchInputOptions): UseSearchInputReturn => {
  const router = useRouter();
  const [value, setValue] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [isTextareaMultiLine, setIsTextareaMultiLine] = useState(false);
  const [isFromTemplate, setIsFromTemplate] = useState(false);
  const [selectedTipIndex, setSelectedTipIndex] = useState<number | null>(null);
  const [templateFieldValues, setTemplateFieldValues] = useState<Record<string, string>>({});
  const [templateFieldErrors, setTemplateFieldErrors] = useState<Record<string, boolean>>({});

  const hasText = isFromTemplate
    ? selectedTipIndex !== null && tipData
      ? tipData[selectedTipIndex].fields.every((f) => !!templateFieldValues[f.key]?.trim())
      : false
    : value.trim().length > 0;

  const setTemplateFieldValue = useCallback((key: string, val: string) => {
    setTemplateFieldValues((prev) => ({ ...prev, [key]: val }));
    setTemplateFieldErrors((prev) => ({ ...prev, [key]: false }));
  }, []);

  const resetTemplateFields = useCallback(() => {
    setTemplateFieldValues({});
    setTemplateFieldErrors({});
  }, []);

  const handleSubmit = useCallback((queryOverride?: string) => {
    // Lexical 기반 TemplateInput에서 직접 쿼리를 넘겨주는 경우
    if (typeof queryOverride === 'string') {
      const trimmed = queryOverride.trim();
      if (!trimmed) return;
      const sessionId = crypto.randomUUID();
      let url = `/chat/${sessionId}?q=${encodeURIComponent(trimmed)}`;
      if (selectedSources?.length) {
        url += `&sources=${selectedSources.join(',')}`;
      }
      router.push(url);
      return;
    }

    if (isFromTemplate && selectedTipIndex !== null && tipData) {
      const tip = tipData[selectedTipIndex];
      const errors: Record<string, boolean> = {};
      let hasEmpty = false;
      for (const field of tip.fields) {
        if (!templateFieldValues[field.key]?.trim()) {
          errors[field.key] = true;
          hasEmpty = true;
        }
      }
      if (hasEmpty) {
        setTemplateFieldErrors(errors);
        return;
      }
      const query = tip.template
        .map((seg) =>
          typeof seg === 'string' ? seg : (templateFieldValues[seg.field] ?? ''),
        )
        .join('');
      const sessionId = crypto.randomUUID();
      let url = `/chat/${sessionId}?q=${encodeURIComponent(query)}`;
      if (selectedSources?.length) {
        url += `&sources=${selectedSources.join(',')}`;
      }
      router.push(url);
    } else {
      const trimmed = value.trim();
      if (!trimmed) return;
      const sessionId = crypto.randomUUID();
      let url = `/chat/${sessionId}?q=${encodeURIComponent(trimmed)}`;
      if (selectedSources?.length) {
        url += `&sources=${selectedSources.join(',')}`;
      }
      router.push(url);
    }
  }, [isFromTemplate, selectedTipIndex, tipData, templateFieldValues, value, router, selectedSources]);

  // 템플릿 모드에서는 textarea가 숨겨져 있으므로 항상 multiline
  const isMultiLine = isFromTemplate || isTextareaMultiLine;

  // Textarea 자동 높이 조절
  useEffect(() => {
    if (!inputRef.current) return;
    inputRef.current.style.height = 'auto';
    const scrollHeight = inputRef.current.scrollHeight;
    inputRef.current.style.height = Math.min(scrollHeight, 26 * 6) + 'px';
    // 1줄 높이(~26px)를 초과하면 multiline
    setIsTextareaMultiLine(scrollHeight > 30);
  }, [value, inputRef]);

  return {
    value,
    setValue,
    hasText,
    isMultiLine,
    isFocused,
    setIsFocused,
    isFromTemplate,
    setIsFromTemplate,
    selectedTipIndex,
    setSelectedTipIndex,
    templateFieldValues,
    setTemplateFieldValue,
    templateFieldErrors,
    setTemplateFieldErrors,
    resetTemplateFields,
    handleSubmit,
  };
};
