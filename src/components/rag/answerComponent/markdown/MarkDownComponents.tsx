import type { Components } from 'react-markdown';
import { renderWithBadges } from './renderWithBadges';

export const MarkDownComponents = (sources?: ChatSource[]): Components => ({
  table: ({ node, ...props }) => (
    <div className="table-wrapper">
      <table {...props} />
    </div>
  ),

  // strong 내 코드 처리
  code: ({ className, children, ...props }) => {
    const isCodeBlock = typeof className === 'string' && className.includes('language-');

    // 인라인 코드만 커스텀 처리
    if (!isCodeBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }

    // 코드블록은 기본 렌더링 (react-markdown이 pre로 감싸줌)
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },

  strong: ({ node, children, ...props }) => {
    return (
      <strong {...props} style={{ fontWeight: 600 }}>
        {children}
      </strong>
    );
  },

  // 줄바꿈 처리 (enter 1번 = <br/>, 2번 이상 = 새 문단)
  p: ({ node, children, ...props }) => {
    return <p {...props}>{children}</p>;
  },

  // text 노드에서 [n] 치환
  text: ({ children }) => {
    const value = typeof children === 'string' ? children : String(children ?? '');
    return <>{renderWithBadges(value, sources)}</>;
  },
});
