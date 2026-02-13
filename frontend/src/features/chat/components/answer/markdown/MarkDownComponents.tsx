import React from 'react';
import type { Components } from 'react-markdown';

import type { ChatSource } from '@/features/chat/types';

import { renderWithBadges } from './renderWithBadges';

const processChildren = (children: React.ReactNode, sources?: ChatSource[]) => {
  return React.Children.map(children, (child) => {
    if (typeof child === 'string') {
      return renderWithBadges(child, sources);
    }
    return child;
  });
};

export const MarkDownComponents = (sources?: ChatSource[]): Components => {
  return {
    // 표 관련 컴포넌트
    table: ({ children }) => (
      <div className="table-wrapper">
        <table>{children}</table>
      </div>
    ),
    caption: ({ children }) => <caption>{processChildren(children, sources)}</caption>,
    thead: ({ children }) => <thead>{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr>{children}</tr>,
    th: ({ children, style }) => (
      <th style={style}>{processChildren(children, sources)}</th>
    ),
    td: ({ children, style }) => (
      <td style={style}>{processChildren(children, sources)}</td>
    ),

    code: ({ className, children, ...props }) => {
      const isCodeBlock = typeof className === 'string' && className.includes('language-');

      if (!isCodeBlock) {
        return (
          <code className={className} {...props}>
            {processChildren(children, sources)}
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
      <strong style={{ fontWeight: 600 }}>
        {processChildren(children, sources)}
      </strong>
    ),

    p: ({ children }) => <p>{processChildren(children, sources)}</p>,

    li: ({ children }) => <li>{processChildren(children, sources)}</li>,

    h1: ({ children }) => <h1>{processChildren(children, sources)}</h1>,

    h2: ({ children }) => <h2>{processChildren(children, sources)}</h2>,

    h3: ({ children }) => <h3>{processChildren(children, sources)}</h3>,
  };
};
