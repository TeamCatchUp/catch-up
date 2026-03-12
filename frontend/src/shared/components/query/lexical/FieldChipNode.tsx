'use client';

import type { ReactNode } from 'react';
import type { DOMExportOutput, LexicalNode, NodeKey, SerializedLexicalNode, Spread } from 'lexical';
import { $applyNodeReplacement, DecoratorNode } from 'lexical';

import FieldChipComponent from './FieldChipComponent';

export type SerializedFieldChipNode = Spread<{ fieldKey: string; placeholder: string }, SerializedLexicalNode>;

export class FieldChipNode extends DecoratorNode<ReactNode> {
  __fieldKey: string;
  __placeholder: string;

  static getType(): string {
    return 'field-chip';
  }

  static clone(node: FieldChipNode): FieldChipNode {
    return new FieldChipNode(node.__fieldKey, node.__placeholder, node.__key);
  }

  constructor(fieldKey: string, placeholder: string, key?: NodeKey) {
    super(key);
    this.__fieldKey = fieldKey;
    this.__placeholder = placeholder;
  }

  getFieldKey(): string {
    return this.getLatest().__fieldKey;
  }

  // --- DOM ---

  createDOM(): HTMLElement {
    const span = document.createElement('span');
    span.setAttribute('data-field-key', this.__fieldKey);
    span.contentEditable = 'false';
    span.style.display = 'inline';
    return span;
  }

  updateDOM(): boolean {
    return false;
  }

  exportDOM(): DOMExportOutput {
    const el = document.createElement('span');
    el.textContent = `[${this.__placeholder}]`;
    return { element: el };
  }

  // --- Inline ---

  isInline(): boolean {
    return true;
  }

  // --- Serialization ---

  static importJSON(json: SerializedFieldChipNode): FieldChipNode {
    return $createFieldChipNode(json.fieldKey, json.placeholder);
  }

  exportJSON(): SerializedFieldChipNode {
    return {
      ...super.exportJSON(),
      fieldKey: this.__fieldKey,
      placeholder: this.__placeholder,
      type: 'field-chip',
      version: 1,
    };
  }

  // --- React Decorator ---

  decorate(): ReactNode {
    return <FieldChipComponent fieldKey={this.__fieldKey} placeholder={this.__placeholder} nodeKey={this.__key} />;
  }
}

export function $createFieldChipNode(fieldKey: string, placeholder: string): FieldChipNode {
  return $applyNodeReplacement(new FieldChipNode(fieldKey, placeholder));
}

export function $isFieldChipNode(node: LexicalNode | null | undefined): node is FieldChipNode {
  return node instanceof FieldChipNode;
}
