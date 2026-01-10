const ToolTip = ({ text }: { text: string }) => {
  return (
    <div className="shadow-tooltip bg-alpha-black-75 point-events-none absolute -top-10 left-0 z-50 flex items-center justify-center rounded-lg px-2.5 py-1.5 whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100">
      <span className="text-label-small text-white">{text}</span>
    </div>
  );
};

export default ToolTip;
