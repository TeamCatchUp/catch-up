import { cn } from '@/shared/utils/cn';

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('bg-skeleton-bone animate-pulse rounded-md', className)} {...props} />;
}

export { Skeleton };
