import React from 'react';
import type { Components } from 'react-markdown';

import type { ChatSource } from '@/features/chat/types';

import { renderWithBadges } from './renderWithBadges';

const processChildren = (children: React.ReactNode, sources?: ChatSource[], citationOrderMap?: Map<number, number>) => {
  return React.Children.map(children, (child) => {
    if (typeof child === 'string') {
      return renderWithBadges(child, sources, citationOrderMap);
    }
    return child;
  });
};

export const MarkDownComponents = (sources?: ChatSource[], citationOrderMap?: Map<number, number>): Components => {
  return {
    // 표 관련 컴포넌트
    table: ({ children }) => (
      <div className="table-wrapper">
        <table>{children}</table>
      </div>
    ),
    caption: ({ children }) => <caption>{processChildren(children, sources, citationOrderMap)}</caption>,
    thead: ({ children }) => <thead>{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr>{children}</tr>,
    th: ({ children, style }) => <th style={style}>{processChildren(children, sources, citationOrderMap)}</th>,
    td: ({ children, style }) => <td style={style}>{processChildren(children, sources, citationOrderMap)}</td>,

    code: ({ className, children, ...props }) => {
      const isCodeBlock = typeof className === 'string' && className.includes('language-');

      if (!isCodeBlock) {
        return (
          <code className={className} {...props}>
            {processChildren(children, sources, citationOrderMap)}
          </code>
        );
      }

      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },

    strong: ({ children }) => (
      <strong style={{ fontWeight: 600 }}>{processChildren(children, sources, citationOrderMap)}</strong>
    ),

    p: ({ children }) => <p>{processChildren(children, sources, citationOrderMap)}</p>,

    li: ({ children }) => <li>{processChildren(children, sources, citationOrderMap)}</li>,

    h1: ({ children }) => <h1>{processChildren(children, sources, citationOrderMap)}</h1>,

    h2: ({ children }) => <h2>{processChildren(children, sources, citationOrderMap)}</h2>,

    h3: ({ children }) => <h3>{processChildren(children, sources, citationOrderMap)}</h3>,
  };
};
