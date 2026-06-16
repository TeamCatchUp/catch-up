import AgentEditorLeftPane from './AgentEditorLeftPane';
import AgentEditorSettings from './AgentEditorSettings';

export default function AgentStudioEditorPage() {
  return (
    <div className="bg-background-normal-normal flex h-full min-h-0 overflow-hidden">
      <AgentEditorLeftPane />
      <AgentEditorSettings />
    </div>
  );
}
