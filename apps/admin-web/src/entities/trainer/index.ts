import type { Brand } from '@/shared/lib/brand'

export type TrainerId = Brand<string, 'TrainerId'>

export interface Trainer {
  id: TrainerId
  fullName: string
  phone: string | null
  isActive: boolean
  createdAt: string // ISO datetime
  updatedAt: string // ISO datetime
}
