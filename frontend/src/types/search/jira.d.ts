export interface JiraNode {
  id: string;
  name: string;
  type: 'project' | 'board' | 'ticket';
  isPublic: boolean;
  lastEdited: string;
  children?: JiraNode[];
}
