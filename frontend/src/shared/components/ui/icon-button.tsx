import { cn } from '@/shared/utils/cn';

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export default function IconButton({ children, className, ...props }: IconButtonProps) {
  return (
    <button
      className={cn('icon-button-only-gray flex h-9 w-9 cursor-pointer items-center justify-center p-1.5', className)}
      {...props}
    >
      {children}
    </button>
  );
}
