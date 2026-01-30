import clsx from 'clsx';

export type SourceType = 'jira' | 'github';

const SourceBadge = ({ n, sourceType }: { n: string; sourceType: SourceType }) => {
  return (
    <span
      className={clsx(
        'relative -top-0.5 mr-px inline-flex h-6 w-6.5 items-center justify-center rounded-full whitespace-nowrap',
        sourceType === 'jira' ? 'bg-green-10' : 'bg-blue-5',
      )}
    >
      <span className="text-body-xsmall text-gray-80 relative top-[0.5px]">{n}</span>
    </span>
  );
};

export default SourceBadge;
