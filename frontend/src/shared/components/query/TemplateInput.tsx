'use client';

import { RefObject, useCallback, useEffect, useMemo, useRef } from 'react';
import { InitialConfigType, LexicalComposer } from '@lexical/react/LexicalComposer';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { PlainTextPlugin } from '@lexical/react/LexicalPlainTextPlugin';
import { $createParagraphNode, $createTextNode, $getRoot, $isParagraphNode, COMMAND_PRIORITY_HIGH, KEY_ENTER_COMMAND } from 'lexical';

import type { UseSearchInputReturn } from '@/shared/hooks/query/useSearchInput';
import type { TipData } from '@/shared/types/template';

import { TemplateFieldContext, type TemplateFieldContextValue } from './lexical/FieldChipComponent';
import { $createFieldChipNode, FieldChipNode } from './lexical/FieldChipNode';

// ─── Props ──────────────────────────────────────────────────
interface TemplateInputProps {
  tip: TipData;
  input: UseSearchInputReturn;
  submitButtonRef?: RefObject<HTMLButtonElement | null>;
  /** 외부에서 호출 가능한 submit 함수가 준비되면 호출되는 콜백 */
  onSubmitReady?: (submitFn: () => void) => void;
}

// ─── InitPlugin: 에디터 초기 상태 설정 ─────────────────────
function InitPlugin({ tip, onReady }: { tip: TipData; onReady?: () => void }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    queueMicrotask(() => {
      editor.update(() => {
        const root = $getRoot();
        root.clear();
        const paragraph = $createParagraphNode();

        for (const segment of tip.template) {
          if (typeof segment === 'string') {
            paragraph.append($createTextNode(segment));
          } else {
            const field = tip.fields.find((f) => f.key === segment.field);
            if (field) {
              paragraph.append($createFieldChipNode(field.key, field.placeholder));
            }
          }
        }

        root.append(paragraph);
      });
      // editor.update 완료 후 FieldChipComponent 마운트 + ref 등록 대기
      requestAnimationFrame(() => onReady?.());
    });
  }, [editor, tip, onReady]);

  return null;
}

// ─── SubmitPlugin: Enter → submit ───────────────────────────
function SubmitPlugin({ onSubmit }: { onSubmit: () => void }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    return editor.registerCommand(
      KEY_ENTER_COMMAND,
      (event) => {
        if (event?.shiftKey) return false;
        event?.preventDefault();
        onSubmit();
        return true;
      },
      COMMAND_PRIORITY_HIGH,
    );
  }, [editor, onSubmit]);

  return null;
}

// ─── ExitOnAllChipsRemovedPlugin: 칩이 전부 삭제되면 textarea로 전환 ──
function ExitOnAllChipsRemovedPlugin({ input }: { input: UseSearchInputReturn }) {
  const [editor] = useLexicalComposerContext();
  const initializedRef = useRef(false);

  useEffect(() => {
    return editor.registerMutationListener(FieldChipNode, (mutations) => {
      // 초기 생성(InitPlugin)은 무시
      if (!initializedRef.current) {
        initializedRef.current = true;
        return;
      }

      // 삭제가 발생했을 때만 체크
      const hasDestroyed = [...mutations.values()].includes('destroyed');
      if (!hasDestroyed) return;

      editor.getEditorState().read(() => {
        const root = $getRoot();
        const paragraph = root.getFirstChild();
        if (!paragraph || !$isParagraphNode(paragraph)) return;

        const hasChips = paragraph.getChildren().some((child) => child instanceof FieldChipNode);
        if (!hasChips) {
          // 남은 텍스트를 추출해서 textarea로 전환
          const remainingText = root.getTextContent();
          input.setValue(remainingText);
          input.setIsFromTemplate(false);
          input.setSelectedTipIndex(null);
          input.resetTemplateFields();
        }
      });
    });
  }, [editor, input]);

  return null;
}

// ─── QueryExtractor: 에디터 상태에서 쿼리 추출 ─────────────
function useExtractQuery() {
  const [editor] = useLexicalComposerContext();

  return useCallback(
    (fieldValues: Record<string, string>): string => {
      let query = '';
      editor.getEditorState().read(() => {
        const root = $getRoot();
        const paragraph = root.getFirstChild();
        if (!paragraph || !$isParagraphNode(paragraph)) return;

        const children = paragraph.getChildren();
        for (const child of children) {
          if (child instanceof FieldChipNode) {
            query += fieldValues[child.getFieldKey()] ?? '';
          } else {
            query += child.getTextContent();
          }
        }
      });
      return query;
    },
    [editor],
  );
}

// ─── Main Component ─────────────────────────────────────────
export default function TemplateInput({ tip, input, submitButtonRef, onSubmitReady }: TemplateInputProps) {
  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});
  const fieldKeys = useMemo(
    () => tip.template.filter((seg): seg is { field: string } => typeof seg !== 'string').map((seg) => seg.field),
    [tip.template],
  );

  // Lexical 에디터 설정
  const initialConfig: InitialConfigType = useMemo(
    () => ({
      namespace: 'TemplateInput',
      nodes: [FieldChipNode],
      onError: () => {},
      editable: true,
    }),
    [],
  );

  const registerFieldRef = useCallback((key: string, el: HTMLElement | null) => {
    if (el) {
      fieldRefs.current[key] = el;
    } else {
      delete fieldRefs.current[key];
    }
  }, []);

  const focusField = useCallback((key: string) => {
    fieldRefs.current[key]?.focus();
  }, []);

  const focusSubmitButton = useCallback(() => {
    submitButtonRef?.current?.focus();
  }, [submitButtonRef]);

  // InitPlugin 완료 후 첫 필드 포커스
  const handleInitReady = useCallback(() => {
    const firstKey = fieldKeys[0];
    if (firstKey) {
      fieldRefs.current[firstKey]?.focus();
    }
  }, [fieldKeys]);

  const { templateFieldValues, templateFieldErrors, setTemplateFieldValue, setIsFocused } = input;

  // Context value (칩 컴포넌트가 상태에 접근)
  const contextValue: TemplateFieldContextValue = useMemo(
    () => ({
      fieldValues: templateFieldValues,
      fieldErrors: templateFieldErrors,
      setFieldValue: setTemplateFieldValue,
      onSubmit: () => {},
      onFocus: () => setIsFocused(true),
      fieldKeys,
      registerFieldRef,
      focusField,
      focusSubmitButton,
    }),
    [templateFieldValues, templateFieldErrors, setTemplateFieldValue, setIsFocused, fieldKeys, registerFieldRef, focusField, focusSubmitButton],
  );

  // onSubmit을 SubmitBridge가 설정한 후 context에 반영하기 위한 ref
  const submitRef = useRef<() => void>(() => {});

  const contextWithSubmit: TemplateFieldContextValue = useMemo(
    () => ({
      ...contextValue,
      onSubmit: () => submitRef.current(),
    }),
    [contextValue],
  );

  return (
    <div className="text-body-medium min-h-10 cursor-text leading-[1.7]" onClick={() => input.setIsFocused(true)}>
      <LexicalComposer initialConfig={initialConfig}>
        <TemplateFieldContext.Provider value={contextWithSubmit}>
          <PlainTextPlugin
            contentEditable={<ContentEditable className="text-content-neutral outline-none" />}
            ErrorBoundary={LexicalErrorBoundary}
          />
          <InitPlugin tip={tip} onReady={handleInitReady} />
          <ExitOnAllChipsRemovedPlugin input={input} />
          <SubmitBridgeWithRef input={input} submitRef={submitRef} onSubmitReady={onSubmitReady} fieldKeys={fieldKeys} fieldRefs={fieldRefs} />
        </TemplateFieldContext.Provider>
      </LexicalComposer>
    </div>
  );
}

// ─── SubmitBridgeWithRef: submit + validation + 외부 노출 ───
function SubmitBridgeWithRef({
  input,
  submitRef,
  onSubmitReady,
  fieldKeys,
  fieldRefs,
}: {
  input: UseSearchInputReturn;
  submitRef: React.RefObject<() => void>;
  onSubmitReady?: (submitFn: () => void) => void;
  fieldKeys: string[];
  fieldRefs: React.RefObject<Record<string, HTMLElement | null>>;
}) {
  const extractQuery = useExtractQuery();

  const handleSubmit = useCallback(() => {
    // 빈 필드 validation
    const errors: Record<string, boolean> = {};
    let hasEmpty = false;
    for (const key of fieldKeys) {
      if (!input.templateFieldValues[key]?.trim()) {
        errors[key] = true;
        hasEmpty = true;
      }
    }
    if (hasEmpty) {
      input.setTemplateFieldErrors(errors);
      const firstError = fieldKeys.find((key) => errors[key]);
      if (firstError) fieldRefs.current[firstError]?.focus();
      return;
    }

    const query = extractQuery(input.templateFieldValues);
    input.handleSubmit(query);
  }, [extractQuery, input, fieldKeys, fieldRefs]);

  // context onSubmit용 ref 업데이트
  const localSubmitRef = submitRef as { current: () => void };
  useEffect(() => {
    localSubmitRef.current = handleSubmit;
  }, [handleSubmit, localSubmitRef]);

  // 외부(submit 버튼)에 최신 submit 함수 전달
  useEffect(() => {
    onSubmitReady?.(handleSubmit);
  }, [handleSubmit, onSubmitReady]);

  return <SubmitPlugin onSubmit={handleSubmit} />;
}
