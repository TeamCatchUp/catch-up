'use client';

interface OnboardingLayoutProps {
  children: React.ReactNode;
}

export function OnboardingLayout({ children }: OnboardingLayoutProps) {
  return (
    <div className="bg-onboarding-gradient flex size-full flex-col items-center px-30 py-20">
      <div className="flex h-167.5 w-full max-w-110 flex-col items-start justify-between">{children}</div>
    </div>
  );
}
