interface SubTask {
  id: number;
  title: string;
}

interface Task {
  id: number;
  title: string;
  subtasks: SubTask[];
}
