import IconAddSmall from '@/public/icons/icon/add_small.svg';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

import type { PermissionMember } from '../../types/adminPermissionModel';

interface AdminGrantSectionProps {
  members: PermissionMember[];
  selectedMemberId: number | null;
  reason: string;
  onMemberChange: (memberId: number) => void;
  onReasonChange: (reason: string) => void;
  onOpenGrantModal: () => void;
  disabled?: boolean;
}

/** Admin 권한 부여 섹션 */
const AdminGrantSection = ({
  members,
  selectedMemberId,
  reason,
  onMemberChange,
  onReasonChange,
  onOpenGrantModal,
  disabled = false,
}: AdminGrantSectionProps) => {
  const isSubmitDisabled = disabled || !selectedMemberId || !reason.trim();

  return (
    <section className="border-edge-neutral bg-fill-normal flex w-250 flex-col gap-2">
      <div className="flex h-9 items-center justify-between">
        <h2 className="text-heading-large text-content-normal">Admin 권한 부여하기</h2>
        <Button
          variant="box-solid-primary"
          size="md"
          className="text-heading-small h-9 w-[99px]"
          onClick={onOpenGrantModal}
          disabled={isSubmitDisabled}
        >
          <IconAddSmall className="size-6 shrink-0" />
          부여하기
        </Button>
      </div>

      <div className="border-edge-neutral flex items-start gap-5 rounded-xl border px-5 py-5">
        <div className="flex w-[470px] flex-col gap-1.5">
          <span className="text-body-small text-content-normal">멤버</span>
          <Select
            value={selectedMemberId != null ? String(selectedMemberId) : ''}
            onValueChange={(v) => onMemberChange(Number(v))}
            disabled={disabled}
          >
            <SelectTrigger className="h-[46px]">
              <SelectValue placeholder="멤버 선택" />
            </SelectTrigger>
            <SelectContent>
              {members.map((member) => (
                <SelectItem key={member.id} value={String(member.id)}>
                  {member.name} ({member.department})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex w-[470px] flex-col gap-1.5">
          <span className="text-body-small text-content-normal">부여 사유</span>
          <Input
            value={reason}
            onChange={(event) => onReasonChange(event.target.value)}
            placeholder="부여 사유를 작성해주세요."
            className="h-[46px]"
            disabled={disabled}
          />
        </div>
      </div>
    </section>
  );
};

export default AdminGrantSection;
