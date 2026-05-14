import { Button } from '@/shared/ui/button'
import { t } from '@/shared/i18n'

interface Props {
  value: 'true' | 'false' | undefined
  onChange: (value: 'true' | 'false' | undefined) => void
}

const OPTIONS = [
  { label: () => t('trainers.filter.active'), filterVal: 'true' as const },
  { label: () => t('trainers.filter.inactive'), filterVal: 'false' as const },
  { label: () => t('trainers.filter.all'), filterVal: undefined },
] as const

export function ActiveFilterPill({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {OPTIONS.map(({ label, filterVal }) => (
        <Button
          key={label()}
          size="sm"
          variant={value === filterVal ? 'default' : 'outline'}
          onClick={() => onChange(filterVal)}
        >
          {label()}
        </Button>
      ))}
    </div>
  )
}
