export interface JiraNode {
  id: string;
  name: string;
  type: 'project' | 'board' | 'ticket';
  is_public: boolean;
  last_edited: string;
  children?: JiraNode[];
}
