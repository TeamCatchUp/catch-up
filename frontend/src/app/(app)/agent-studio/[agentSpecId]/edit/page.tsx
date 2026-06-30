import { notFound } from 'next/navigation';

import AgentStudioEditorPage from '@/features/agent-studio/components/editor/AgentStudioEditorPage';

interface PageProps {
  params: Promise<{ agentSpecId: string }>;
}

export default async function Page({ params }: PageProps) {
  const { agentSpecId } = await params;
  const parsedAgentSpecId = Number(agentSpecId);

  if (!Number.isInteger(parsedAgentSpecId) || parsedAgentSpecId <= 0) {
    notFound();
  }

  return <AgentStudioEditorPage mode="edit" agentSpecId={parsedAgentSpecId} />;
}
