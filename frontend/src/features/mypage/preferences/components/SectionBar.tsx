'use client';

interface SectionBarProps {
  title: string;
}

export default function SectionBar({ title }: SectionBarProps) {
  return (
    <div className="bg-fill-strong rounded-md px-5 py-1.5">
      <span className="text-heading-small text-content-neutral">{title}</span>
    </div>
  );
}
