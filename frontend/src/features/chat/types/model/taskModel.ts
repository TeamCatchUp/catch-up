/**
 * 단순 서브태스크 모델.
 * @interface SubTaskModel
 */
export interface SubTaskModel {
  id: number;
  title: string;
}

/**
 * 단순 태스크 모델.
 * @interface TaskModel
 */
export interface TaskModel {
  id: number;
  title: string;
  subtasks: SubTaskModel[];
}
