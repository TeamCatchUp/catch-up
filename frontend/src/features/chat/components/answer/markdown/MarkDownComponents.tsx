import React from 'react';
import type { Components } from 'react-markdown';

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
  console.log('MarkDownComponents initialized with sources:', sources);

  return {
    table: ({ children }) => (
      <div className="table-wrapper">
        <table>{children}</table>
      </div>
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
