'use client';

interface TopicHeaderProps {
  topic: string | null;
}

export default function TopicHeader({ topic }: TopicHeaderProps) {
  if (!topic) return null;

  return <h2 className="text-heading-medium text-text-normal-normal h-13 px-6 pt-3 pb-1">{topic}</h2>;
}
