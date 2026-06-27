import type { ButtonHTMLAttributes } from 'react';

import LabIcon from '@/public/icons/icon/lab.svg';
import { cn } from '@/shared/utils/cn';

const AGENT_STUDIO_CREATE_BUTTON_GRADIENT =
  'radial-gradient(97.22% 97.22% at 50% 2.78%, var(--Static-Black, #030303) 0%, #0E0A1E 64.72%, #1C133F 66.03%, #412A9A 77.06%, #1A75FF 91.07%, #69A5FF 100%)';

type AgentCreateButtonProps = ButtonHTMLAttributes<HTMLButtonElement>;

export default function AgentCreateButton({
  className,
  disabled = false,
  type = 'button',
  ...props
}: AgentCreateButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'text-body-small text-static-white inline-flex h-9 shrink-0 cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2.5 py-1.5 focus-visible:outline-none disabled:pointer-events-none disabled:cursor-default',
        className,
      )}
      style={{ backgroundImage: AGENT_STUDIO_CREATE_BUTTON_GRADIENT }}
      disabled={disabled}
      {...props}
    >
      <LabIcon className="size-5 shrink-0" aria-hidden="true" />
      Agent 만들기
    </button>
  );
}
