import type { GithubNode } from '@/constants/githubRepoData';
import type { JiraNode } from '@/constants/jiraData';

/**
 * GitHub 노드와 모든 자식 노드의 ID를 재귀적으로 수집
 */
export const getAllGithubChildIds = (node: GithubNode, ids: string[] = []): string[] => {
  ids.push(node.id);
  if (node.children) {
    node.children.forEach((child) => getAllGithubChildIds(child, ids));
  }
  return ids;
};

/**
 * Jira 노드와 모든 자식 노드의 ID를 재귀적으로 수집
 */
export const getAllJiraChildIds = (node: JiraNode, ids: string[] = []): string[] => {
  ids.push(node.id);
  if (node.children) {
    node.children.forEach((child) => getAllJiraChildIds(child, ids));
  }
  return ids;
};

/**
 * 일반적인 트리 노드에서 모든 자식 ID를 수집하는 제네릭 함수
 */
export const getAllChildIds = <T extends { id: string; children?: T[] }>(
  node: T,
  ids: string[] = [],
): string[] => {
  ids.push(node.id);
  if (node.children) {
    node.children.forEach((child) => getAllChildIds(child, ids));
  }
  return ids;
};
