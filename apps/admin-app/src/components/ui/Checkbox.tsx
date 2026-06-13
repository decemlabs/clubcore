import { useEffect, useRef } from 'react';
import { cn } from '@/lib/cn';
import { Check } from '@/components/icons';

/** Кастомный чекбокс (appearance-none) с поддержкой indeterminate. */
export function Checkbox({
  checked,
  indeterminate = false,
  onCheckedChange,
  className,
  ...props
}: {
  checked: boolean;
  indeterminate?: boolean;
  onCheckedChange: (checked: boolean) => void;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, 'checked' | 'onChange' | 'type'>) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <span className={cn('relative inline-grid size-4 shrink-0 place-items-center', className)}>
      <input
        ref={ref}
        type="checkbox"
        checked={checked}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="peer size-4 cursor-pointer appearance-none rounded-[5px] border-[1.5px] border-border-strong bg-surface transition-colors checked:border-fg checked:bg-fg indeterminate:border-fg indeterminate:bg-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface"
        {...props}
      />
      <Check
        className="pointer-events-none absolute hidden size-3 text-bg peer-checked:block peer-indeterminate:hidden"
        strokeWidth={3.5}
      />
      <span className="pointer-events-none absolute hidden h-[2px] w-2 rounded-full bg-bg peer-indeterminate:block" />
    </span>
  );
}
