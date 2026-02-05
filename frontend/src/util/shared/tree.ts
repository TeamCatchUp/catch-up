/** 트리 노드 기본 인터페이스 */
export interface TreeNode {
  id: string;
  children?: TreeNode[];
}

/**
 * 트리 노드에서 모든 자식 ID를 재귀적으로 수집하는 순수 함수
 * 입력 배열을 변경하지 않고 새 배열을 반환
 */
export const getAllChildIds = <T extends TreeNode>(node: T): string[] => {
  const childIds = node.children?.flatMap((child) => getAllChildIds(child as T)) ?? [];
  return [node.id, ...childIds];
};

/**
 * 트리 노드와 모든 자식 노드를 평탄화된 배열로 반환
 * 입력 배열을 변경하지 않고 새 배열을 반환
 */
export const getAllChildNodes = <T extends TreeNode>(node: T): T[] => {
  const children = (node.children as T[] | undefined)?.flatMap((child) => getAllChildNodes(child)) ?? [];
  return [node, ...children];
};

/**
 * 트리 노드 배열을 평탄화된 단일 배열로 반환
 * 입력 배열을 변경하지 않고 새 배열을 반환
 */
export const getAllNodesFlat = <T extends TreeNode>(nodes: T[]): T[] => {
  return nodes.flatMap((node) => getAllChildNodes(node));
};
