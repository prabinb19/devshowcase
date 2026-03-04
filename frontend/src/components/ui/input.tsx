import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = "", id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="mb-1 block text-sm font-bold text-win98-black"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`w-full bevel-inset bg-white px-3 py-2 text-sm text-win98-black focus:outline-dotted focus:outline-2 focus:outline-win98-black ${
            error ? "border-win98-red" : ""
          } ${className}`}
          {...props}
        />
        {error && (
          <p className="mt-1 text-xs text-win98-red font-bold">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
