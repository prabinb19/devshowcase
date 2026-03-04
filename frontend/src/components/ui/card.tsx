interface CardProps {
  children: React.ReactNode;
  className?: string;
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export function Card({ children, className = "", header, footer }: CardProps) {
  return (
    <div className={`bg-win98-silver bevel-outset ${className}`}>
      {header && (
        <div className="win98-titlebar">
          {header}
        </div>
      )}
      <div className="bevel-inset bg-white m-1 p-3">{children}</div>
      {footer && (
        <>
          <div className="groove-hr mx-1" />
          <div className="px-3 py-2">{footer}</div>
        </>
      )}
    </div>
  );
}
