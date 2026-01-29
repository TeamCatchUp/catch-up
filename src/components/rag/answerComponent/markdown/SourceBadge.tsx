import clsx from 'clsx';

export type SourceType = 'jira' | 'github';

const SourceBadge = ({ n, sourceType }: { n: string; sourceType: SourceType }) => {
  return (
    <div
      className={clsx(
        'mr-px h-6 w-6.5 items-center justify-center rounded-full px-2 py-1 whitespace-nowrap',
        sourceType === 'jira' ? 'bg-green-10' : 'bg-blue-5',
      )}
    >
      <span className="text-body-xsmall text-gray-80 relative bottom-px">{n}</span>
    </div>
  );
};

export default SourceBadge;
