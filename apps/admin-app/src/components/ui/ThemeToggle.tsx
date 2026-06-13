import { Moon, Sun } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';
import { useTheme } from '@/hooks/use-theme';

/** Переключатель светлой/тёмной темы. Иконка-кнопка под стиль действий в шапке. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';
  const label = isDark ? 'Включить светлую тему' : 'Включить тёмную тему';

  return (
    <Button
      variant="outline"
      size="icon"
      aria-label={label}
      title={label}
      className={cn('size-[38px] rounded-full', className)}
      onClick={toggleTheme}
    >
      {isDark ? <Sun className="size-[17px]" /> : <Moon className="size-[17px]" />}
    </Button>
  );
}
