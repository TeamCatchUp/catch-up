'use client';

import { useState } from 'react';

import { cn } from '@/shared/utils/cn';

import Connector from '/public/icons/icon/connector.svg';
import LastConnector from '/public/icons/icon/last_connector.svg';
import Link from '/public/icons/icon/link.svg';
import LoadingProfile from '/public/icons/icon/loading_profile.svg';

interface Reply {
  id: number;
  author: string;
  timestamp: string;
  content: string;
  attachment?: {
    title: string;
    url: string;
  };
}

interface Comment {
  id: number;
  author: string;
  timestamp: string;
  content: string;
  attachment?: {
    title: string;
    url: string;
  };
  replies: Reply[];
}

// MOCK 데이터
const MOCK_COMMENTS: Comment[] = [
  {
    id: 1,
    author: '직원04',
    timestamp: '2025.09.01 09:30',
    content: '답글 無 댓글 text texttext texttext text text texttext texttext texttext texttext text',
    attachment: {
      title: '일본 시장 진출 전략 수립 및 초기 셋업',
      url: '#',
    },
    replies: [],
  },
  {
    id: 2,
    author: '직원042',
    timestamp: '2025.09.01 10:30',
    content: '답글 有 댓글 ',
    replies: [
      {
        id: 21,
        author: '박민수',
        timestamp: '2025.09.01 10:40',
        content: '답글1',
        attachment: {
          title: '일본 시장 진출 전략 수립 및 초기 셋업2',
          url: '#',
        },
      },
      {
        id: 22,
        author: '박민수2',
        timestamp: '2025.09.01 10:50',
        content: '댓글 text text text text text text text text text text text text text text',
      },
      {
        id: 23,
        author: '박민수3',
        timestamp: '2025.09.02 10:40',
        content:
          '답글3 tetxdsdkt ksdadlsfdsjf adskf ja;kls jfasdjf k;f jadsk;fj kasld;j fklsf;klf jasdkl;fj sadj flasjflajsfksak;dks;f ja;ksjk;',
      },
    ],
  },
];

const CommentsTabContent = () => {
  const [expandedComments, setExpandedComments] = useState<Set<number>>(new Set());

  const toggleReplies = (commentId: number) => {
    setExpandedComments((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(commentId)) {
        newSet.delete(commentId);
      } else {
        newSet.add(commentId);
      }
      return newSet;
    });
  };

  const renderReplies = (replies: Reply[], isExpanded: boolean, commentId: number) => {
    if (replies.length === 0) return null;

    // closed 답글 (?개의 답글 더보기)
    if (!isExpanded) {
      return (
        <div className="-mt-1 ml-2.75 flex h-11.75 items-center">
          <LastConnector className="mr-0.5" />
          <div className="flex">
            <LoadingProfile className="h-6.25 w-6.25" />
            <LoadingProfile className="relative right-1.5 h-6.25 w-6.25" />
          </div>
          <button
            onClick={() => toggleReplies(commentId)}
            className="group text-button-primary-blue flex cursor-pointer items-center justify-center px-1.5 py-1"
          >
            <span className="text-body-xsmall text-blue-55 group-active:text-blue-60!">
              {replies.length}개의 답글 더보기
            </span>
          </button>
        </div>
      );
    }

    // expanded 답글
    return (
      <div className="-mt-1 ml-2.75 flex flex-col">
        {replies.map((reply, index) => {
          const isLast = index === replies.length - 1;
          const hasMultipleReplies = replies.length > 1;

          return (
            <div key={reply.id} className="flex flex-col">
              <div className="flex gap-0">
                {isLast ? <LastConnector className="mr-0.5" /> : <Connector className="mr-0.5" />}
                <div className="flex items-center gap-1.5">
                  <LoadingProfile className="h-6.25 w-6.25" />
                  <div className="flex items-center gap-2">
                    <span className="text-body-small text-gray-70">{reply.author}</span>
                    <span className="text-body-xsmall text-gray-30">{reply.timestamp}</span>
                  </div>
                </div>
              </div>
              <div
                className={cn(
                  'text-body-small text-gray-70 -mt-2',
                  !isLast && hasMultipleReplies ? 'border-neutral-3 border-l pl-12.5' : 'ml-12.5',
                )}
              >
                {reply.content}
              </div>
              {reply.attachment && (
                <div className={cn(!isLast && hasMultipleReplies && 'border-neutral-3 border-l pl-0')}>
                  <div className="bg-neutral-1 border-neutral-3 mt-1.5 ml-12.5 flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
                    <Link className="h-5 w-5 text-gray-50" />
                    <span className="text-body-small text-gray-70">{reply.attachment.title}</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-5">
      {MOCK_COMMENTS.map((comment) => {
        const hasReplies = comment.replies.length > 0;
        const isExpanded = expandedComments.has(comment.id);

        return (
          <div key={comment.id} className="flex flex-col gap-0.5">
            {/* 댓글 사용자 */}
            <div className="flex items-center gap-1.5">
              <LoadingProfile className="h-6.25 w-6.25" />
              <div className="flex items-center gap-2">
                <span className="text-body-small text-gray-70">{comment.author}</span>
                <span className="text-body-xsmall text-gray-30">{comment.timestamp}</span>
              </div>
            </div>

            {/* 댓글 내용 */}
            {hasReplies ? (
              <div className="border-neutral-4 ml-2.75 flex flex-col border-l">
                <div className="text-body-small text-gray-70 ml-4.75">{comment.content}</div>
                {comment.attachment && (
                  <div className="bg-neutral-1 border-neutral-3 mt-1.5 ml-4.75 flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
                    <Link className="h-5 w-5" />
                    <span className="text-body-small text-gray-70">{comment.attachment.title}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-0.5 ml-7.75 flex flex-col">
                <div className="text-body-small text-gray-70">{comment.content}</div>
                {comment.attachment && (
                  <div className="bg-neutral-1 border-neutral-3 mt-1.5 flex cursor-pointer items-center gap-2.5 rounded-xl border px-3 py-1.5">
                    <Link className="h-5 w-5" />
                    <span className="text-body-small text-gray-70">{comment.attachment.title}</span>
                  </div>
                )}
              </div>
            )}

            {/* 답글 렌더링 */}
            {hasReplies && renderReplies(comment.replies, isExpanded, comment.id)}
          </div>
        );
      })}
    </div>
  );
};

export default CommentsTabContent;
