import React from 'react';
import type { Components } from 'react-markdown';

import { renderWithBadges } from './renderWithBadges';

const processChildren = (children: any, sources?: ChatSource[]) => {
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
    table: ({ node, ...props }) => (
      <div className="table-wrapper">
        <table {...props} />
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

    strong: ({ node, children, ...props }) => {
      return (
        <strong {...props} style={{ fontWeight: 600 }}>
          {processChildren(children, sources)}
        </strong>
      );
    },

    p: ({ node, children, ...props }) => {
      return <p {...props}>{processChildren(children, sources)}</p>;
    },

    li: ({ node, children, ...props }) => {
      return <li {...props}>{processChildren(children, sources)}</li>;
    },

    h1: ({ node, children, ...props }) => {
      return <h1 {...props}>{processChildren(children, sources)}</h1>;
    },

    h2: ({ node, children, ...props }) => {
      return <h2 {...props}>{processChildren(children, sources)}</h2>;
    },

    h3: ({ node, children, ...props }) => {
      return <h3 {...props}>{processChildren(children, sources)}</h3>;
    },
  };
};
