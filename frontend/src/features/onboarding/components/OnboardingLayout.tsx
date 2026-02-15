'use client';

interface OnboardingLayoutProps {
  children: React.ReactNode;
}

export function OnboardingLayout({ children }: OnboardingLayoutProps) {
  return (
    <div className="bg-onboarding-gradient flex size-full flex-col items-center px-[120px] py-[80px]">
      <div className="flex h-[670px] w-full max-w-[440px] flex-col items-start justify-between">{children}</div>
    </div>
  );
}
