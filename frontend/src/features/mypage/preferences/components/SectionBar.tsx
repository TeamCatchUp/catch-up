'use client';

interface SectionBarProps {
  title: string;
}

export default function SectionBar({ title }: SectionBarProps) {
  return (
    <div className="bg-fill-normal-strong rounded-md px-5 py-1.5">
      <span className="text-heading-small text-text-normal-neutral">{title}</span>
    </div>
  );
}
