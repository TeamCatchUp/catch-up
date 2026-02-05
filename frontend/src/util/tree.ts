/**
 * 트리 노드에서 모든 자식 ID를 재귀적으로 수집하는 순수 함수
 * 입력 배열을 변경하지 않고 새 배열을 반환
 */
export const getAllChildIds = <T extends { id: string; children?: T[] }>(node: T): string[] => {
  const childIds = node.children?.flatMap((child) => getAllChildIds(child)) ?? [];
  return [node.id, ...childIds];
};
