interface DetailedTaskModalProps {
  onClose: () => void;
  data: {
    type: 'task' | 'subtask';
    taskId: number;
    subId?: Number;
  };
}

const DetailedTaskModal = ({ onClose, data }: DetailedTaskModalProps) => {
  return (
    <div className="">
      <div className="">deatiled Modal</div>
    </div>
  );
};

export default DetailedTaskModal;
