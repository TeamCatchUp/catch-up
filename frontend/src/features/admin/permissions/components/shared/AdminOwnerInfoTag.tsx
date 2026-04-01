import IconHelp from '@/public/icons/icon/help.svg';
import IconInfo from '@/public/icons/icon/info.svg';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/ToolTip';

import {
  ADMIN_OWNER_LABEL,
  ADMIN_OWNER_LINE_1,
  ADMIN_OWNER_LINE_2,
  TAG_BASE_CLASS,
} from '../../constants/permissionsConfig';

/** Admin 권한 소유자 안내 태그 + 툴팁 */
const AdminOwnerInfoTag = () => {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={`${TAG_BASE_CLASS} bg-fill-interaction-hover text-content-alternative inline-flex cursor-default items-center gap-1`}
        >
          <IconInfo className="text-content-alternative size-4 shrink-0" />
          {ADMIN_OWNER_LABEL}
        </span>
      </TooltipTrigger>

      <TooltipContent side="bottom" align="start" size="lg" className="w-90 gap-1">
        <div className="flex h-7 items-center gap-2 self-stretch text-white">
          <IconHelp className="size-5 shrink-0 text-white" />
          <span className="text-body-small">{ADMIN_OWNER_LINE_1}</span>
        </div>
        <p className="text-label-small text-white/75">{ADMIN_OWNER_LINE_2}</p>
      </TooltipContent>
    </Tooltip>
  );
};

export default AdminOwnerInfoTag;
