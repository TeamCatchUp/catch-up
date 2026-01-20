const ToolTip = ({ text }: { text: string | React.ReactNode }) => {
  return (
    <div className="shadow-tooltip bg-alpha-black-75 pointer-events-none absolute z-1000 flex items-center justify-center rounded-lg px-2.5 py-1.5 whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100">
      <span className="text-label-small text-white">{text}</span>
    </div>
  );
};

export default ToolTip;
