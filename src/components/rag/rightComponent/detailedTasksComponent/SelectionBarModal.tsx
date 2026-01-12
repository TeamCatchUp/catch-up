import Epic from '/public/icons/icon/epic.svg';
import DropDownDown from '/public/icons/icon/dropdown_down.svg';
import Cancel from '/public/icons/icon/cancel_small.svg';
import Reply from '/public/icons/icon/reply.svg';
import CheckboxUnchecked from '/public/icons/icon/checkbox_unchecked.svg';
import Task from '/public/icons/icon/task.svg';
import Edit from '/public/icons/icon/edit_square.svg';
import Share from '/public/icons/icon/share_2.svg';

interface SelectionBarModalProps {
  onClose: () => void;
  data: {
    type: 'task' | 'subtask';
    taskId: number;
    subId?: Number;
  };
}

const SelectionBarModal = ({ onClose, data }: SelectionBarModalProps) => {
  return (
    <div className="border-neutral-5 shadow-selection-bar flex w-117 rounded-full border bg-white p-2.5">
      <button className="flex">
        <DropDownDown className="" />
      </button>
      <div className="">체크박스 선택 selection bar</div>
    </div>
  );
};

export default SelectionBarModal;
