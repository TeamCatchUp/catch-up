import clsx from 'clsx';

export type SourceType = 'jira' | 'github';

const SourceBadge = ({ n, sourceType }: { n: string; sourceType: SourceType }) => {
  return (
    <div
      className={clsx(
        'align-center relative top-0.5 flex h-6 items-center justify-center rounded-full px-2 py-1',
        sourceType === 'jira' ? 'bg-green-10' : 'bg-blue-5',
      )}
    >
      <span className="text-body-small text-gray-80">{n}</span>
    </div>
  );
};

export default SourceBadge;
