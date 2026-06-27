'use client';

import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { Button } from '@/shared/components/ui/button';
import { cn } from '@/shared/utils/cn';

import type { StatusImageSource } from './statusImages';

interface StatusActionLink {
  label: string;
  href: string;
}

interface StatusActionBack {
  label: string;
  action: 'back';
}

type StatusAction = StatusActionLink | StatusActionBack;

interface StatusErrorPageProps {
  title: string;
  description: string;
  image: StatusImageSource;
  primaryAction: StatusActionLink;
  secondaryAction?: StatusAction;
  className?: string;
}

function StatusButton({ action, variant }: { action: StatusAction; variant: 'primary' | 'secondary' }) {
  const router = useRouter();
  const buttonVariant = variant === 'primary' ? 'box-solid-primary' : 'box-outline-gray';

  if ('href' in action) {
    return (
      <Button asChild variant={buttonVariant} size="lg" className="h-10">
        <Link href={action.href}>{action.label}</Link>
      </Button>
    );
  }

  return (
    <Button variant={buttonVariant} size="lg" className="h-10" onClick={() => router.back()}>
      {action.label}
    </Button>
  );
}

export default function StatusErrorPage({
  title,
  description,
  image,
  primaryAction,
  secondaryAction,
  className,
}: StatusErrorPageProps) {
  const imageFrame = {
    width: Math.max(image.light.width, image.dark.width),
    height: Math.max(image.light.height, image.dark.height),
  };

  return (
    <div
      className={cn(
        'bg-background-normal-normal flex min-h-full flex-col items-center justify-center gap-9 px-6 py-20',
        className,
      )}
    >
      <div className="flex shrink-0 items-center justify-center" style={imageFrame}>
        <Image
          src={image.light.src}
          width={image.light.width}
          height={image.light.height}
          alt=""
          priority
          className="block dark:hidden"
        />
        <Image
          src={image.dark.src}
          width={image.dark.width}
          height={image.dark.height}
          alt=""
          priority
          className="hidden dark:block"
        />
      </div>
      <div className="flex flex-col items-center gap-2.5 text-center">
        <h1 className="text-heading-xlarge text-text-normal-normal">{title}</h1>
        <p className="text-body-medium text-text-normal-alternative">{description}</p>
      </div>
      <div className="flex items-start gap-4">
        {secondaryAction && <StatusButton action={secondaryAction} variant="secondary" />}
        <StatusButton action={primaryAction} variant="primary" />
      </div>
    </div>
  );
}
