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

  if (tickets.length === 0) return null;

  return (
    <div className="flex w-full flex-col gap-2.5">
      <span className="text-body-xsmall px-1.5 font-medium text-gray-50">{title}</span>

      <div className="no-scrollbar flex w-full items-center gap-2.5 overflow-x-auto pb-1 whitespace-nowrap">
        {tickets.map((ticket, idx) => (
          <span
            key={ticket.id}
            className={clsx(
              'text-body-small text-gray-70 flex shrink-0 cursor-default items-center rounded-full px-4 py-1.5 transition-all hover:brightness-95',
              getTicketColor(idx),
            )}
          >
            {ticket.label}
          </span>
        ))}
      </div>
    </div>
  );
}
