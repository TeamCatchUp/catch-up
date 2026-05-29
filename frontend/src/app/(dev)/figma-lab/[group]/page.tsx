import { notFound } from 'next/navigation';

import FigmaLabRenderer from '../_registry/FigmaLabRenderer';
import { FIGMA_LAB_GROUPS, isFigmaLabGroupId } from '../_registry/groups';

export function generateStaticParams() {
  return FIGMA_LAB_GROUPS.map((group) => ({ group: group.id }));
}

interface PageProps {
  params: Promise<{
    group: string;
  }>;
  searchParams: Promise<{
    case?: string;
  }>;
}

export default async function FigmaLabGroupPage({ params, searchParams }: PageProps) {
  const [{ group }, query] = await Promise.all([params, searchParams]);

  if (!isFigmaLabGroupId(group)) {
    notFound();
  }

  return <FigmaLabRenderer groupId={group} selectedCaseId={query.case} />;
}
