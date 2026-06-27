import type { AgentStudioSelectItem } from '../types/agentStudioModel';
import type { AutomationCredentialItem, AutomationTargetItem } from '../types/automationApi';

export function mapAutomationCredentialToSelectItem(credential: AutomationCredentialItem): AgentStudioSelectItem {
  return {
    value: String(credential.credential_id),
    label: credential.display_name,
    disabled: !credential.is_configured,
  };
}

export function mapAutomationTargetToSelectItem(target: AutomationTargetItem): AgentStudioSelectItem {
  return {
    value: target.target_id,
    label: target.display_name,
    disabled: !target.is_accessible,
  };
}
