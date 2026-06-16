import AgentEditorLeftPane from './AgentEditorLeftPane';
import AgentEditorSettings from './AgentEditorSettings';

export default function AgentStudioEditorPage() {
  return (
    <div className="bg-background-normal-normal flex min-h-full">
      <AgentEditorLeftPane />
      <AgentEditorSettings />
    </div>
  );
}
