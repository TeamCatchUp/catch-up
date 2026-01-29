// import type { Components } from 'react-markdown';
// import { renderWithBadges } from './renderWithBadges';

// export const MarkDownComponents = (sources?: ChatSource[]): Components => ({
//   table: ({ node, ...props }) => (
//     <div className="table-wrapper">
//       <table {...props} />
//     </div>
//   ),

//   // strong 내 코드 처리
//   code: ({ className, children, ...props }) => {
//     const isCodeBlock = typeof className === 'string' && className.includes('language-');

//     // 인라인 코드만 커스텀 처리
//     if (!isCodeBlock) {
//       return (
//         <code className={className} {...props}>
//           {children}
//         </code>
//       );
//     }

//     // 코드블록은 기본 렌더링 (react-markdown이 pre로 감싸줌)
//     return (
//       <code className={className} {...props}>
//         {children}
//       </code>
//     );
//   },

//   strong: ({ node, children, ...props }) => {
//     return (
//       <strong {...props} style={{ fontWeight: 600 }}>
//         {children}
//       </strong>
//     );
//   },

//   // 줄바꿈 처리 (enter 1번 = <br/>, 2번 이상 = 새 문단)
//   p: ({ node, children, ...props }) => {
//     return <p {...props}>{children}</p>;
//   },

//   // text 노드에서 [n] 치환
//   text: ({ children }) => {
//     const value = typeof children === 'string' ? children : String(children ?? '');
//     return <>{renderWithBadges(value, sources)}</>;
//   },
// });
// MarkdownComponents.tsx
import type { Components } from 'react-markdown';
import { renderWithBadges } from './renderWithBadges';
import React from 'react';

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
            {/* {children} */}
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
          {/* {children} */}
          {processChildren(children, sources)}
        </strong>
      );
    },

    p: ({ node, children, ...props }) => {
      // return <p {...props}>{children}</p>;
      return <p {...props}>{processChildren(children, sources)}</p>;
    },

    // text: ({ children }) => {
    //   const value = typeof children === 'string' ? children : String(children ?? '');
    //   console.log('Text node:', { value, sourcesAvailable: !!sources });
    //   const result = renderWithBadges(value, sources);
    //   console.log('Text node result:', result);
    //   return <>{result}</>;
    // },

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
