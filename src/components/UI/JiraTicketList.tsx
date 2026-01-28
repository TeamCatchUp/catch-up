'use client';

import clsx from 'clsx';

interface JiraTicket {
  id: string | number;
  label: string;
}

interface JiraTicketListProps {
  tickets: JiraTicket[];
  title: string;
}

const BG_COLORS = ['bg-violet-5', 'bg-light-blue-5', 'bg-green-5', 'bg-orange-5', 'bg-pink-5', 'bg-blue-5'];

export function JiraTicketList({ tickets, title }: JiraTicketListProps) {
  const getTicketColor = (index: number) => {
    return BG_COLORS[index % BG_COLORS.length];
  };

  // 데이터가 없을 때 아예 컴포넌트를 숨기고 싶다면 기존처럼 null을 유지하고,
  // 안내 문구를 보여주고 싶다면 아래의 렌더링 로직을 따릅니다.

  return (
    <div className="flex w-full flex-col gap-2.5">
      <span className="text-body-xsmall px-1.5 font-medium text-gray-50">{title}</span>

      {tickets.length > 0 ? (
        <div className="no-scrollbar flex w-full items-center gap-2.5 overflow-x-auto pb-1 whitespace-nowrap">
          {tickets.map((ticket, idx) => (
            <span
              key={ticket.id}
              className={clsx(
                'text-body-small text-gray-70 flex shrink-0 cursor-pointer items-center rounded-full px-4 py-1.5 transition-all hover:brightness-95',
                getTicketColor(idx),
              )}
            >
              {ticket.label}
            </span>
          ))}
        </div>
      ) : (
        /* 티켓이 없을 때 보여줄 UI (Empty State) */
        <div className="border-neutral-2 flex w-full items-center justify-center rounded-xl border border-dashed py-4">
          <span className="text-body-xsmall text-gray-30">최근 확인한 티켓이 없습니다.</span>
        </div>
      )}
    </div>
  );
}
