import AgentEditorLeftPane from './AgentEditorLeftPane';
import AgentEditorSettings from './AgentEditorSettings';

export interface AgentStudioEditorPageProps {
  mode?: 'create' | 'edit';
  agentSpecId?: number;
}

export default function AgentStudioEditorPage({ mode = 'create', agentSpecId }: AgentStudioEditorPageProps) {
  return (
    <div className="bg-background-normal-normal flex h-full min-h-0 overflow-hidden">
      <AgentEditorLeftPane />
      <AgentEditorSettings mode={mode} agentSpecId={agentSpecId} />
    </div>
  );
}
