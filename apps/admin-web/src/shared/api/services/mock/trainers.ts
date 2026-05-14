import { faker } from '@faker-js/faker'
import type { Trainer, TrainerId } from '@/entities/trainer'
import { DomainError } from '@/shared/api/errors'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import { createTrainerSchema, updateTrainerSchema } from '@/features/trainers/model/schema'
import type { CreateTrainerInput, UpdateTrainerInput } from '@/features/trainers/model/schema'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'

function role() {
  return useSessionStore.getState().role
}

function ensure(action: 'view' | 'create' | 'edit' | 'delete', resource: 'trainers') {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}

function seedTrainers(): Trainer[] {
  // 8 trainers: 5 active (i < 5), 3 inactive; 50% have phone (even-index i has phone)
  const result: Trainer[] = []
  for (let i = 0; i < 8; i++) {
    const isActive = i < 5
    const hasPhone = i % 2 === 0
    result.push({
      id: faker.string.uuid() as TrainerId,
      fullName: faker.person.fullName(),
      phone: hasPhone ? `+7${faker.string.numeric(10)}` : null,
      isActive,
      createdAt: faker.date.recent({ days: 180 }).toISOString(),
      updatedAt: faker.date.recent({ days: 30 }).toISOString(),
    })
  }
  return result
}

function getDB() {
  const db = loadDB()
  if (!db.trainers || db.trainers.length === 0) {
    db.trainers = seedTrainers()
    saveDB(db)
  }
  return db
}

export const trainers = {
  async list(query: { active?: boolean; page: number; pageSize: number }) {
    await delay()
    ensure('view', 'trainers')
    const db = getDB()
    const filtered =
      query.active !== undefined
        ? db.trainers.filter((t) => t.isActive === query.active)
        : db.trainers
    const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    const total = sorted.length
    const start = (query.page - 1) * query.pageSize
    const items = sorted.slice(start, start + query.pageSize)
    return { items, total, page: query.page, pageSize: query.pageSize }
  },

  async get(id: TrainerId): Promise<Trainer | undefined> {
    await delay()
    ensure('view', 'trainers')
    const db = loadDB()
    return db.trainers.find((t) => t.id === id)
  },

  async create(input: CreateTrainerInput): Promise<Trainer> {
    await delay()
    ensure('create', 'trainers')
    const parsed = createTrainerSchema.safeParse(input)
    if (!parsed.success) {
      const fields: Record<string, string[]> = {}
      for (const issue of parsed.error.issues) {
        const k = String(issue.path[0] ?? 'root')
        ;(fields[k] ??= []).push(issue.message)
      }
      throw new DomainError('validation_failed', 'Проверьте поля', fields)
    }
    const db = loadDB()
    if (!Array.isArray(db.trainers)) {
      db.trainers = seedTrainers()
    }
    // Phone uniqueness check
    if (
      parsed.data.phone &&
      db.trainers.some((t) => t.phone !== null && t.phone === parsed.data.phone)
    ) {
      throw new DomainError('validation_failed', 'Дубликат телефона', {
        phone: ['Тренер с таким телефоном уже существует'],
      })
    }
    const newTrainer: Trainer = {
      id: faker.string.uuid() as TrainerId,
      fullName: parsed.data.fullName,
      phone: parsed.data.phone ?? null,
      isActive: true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    db.trainers = [newTrainer, ...db.trainers]
    saveDB(db)
    return newTrainer
  },

  async update(id: TrainerId, input: UpdateTrainerInput): Promise<Trainer> {
    await delay()
    ensure('edit', 'trainers')
    const parsed = updateTrainerSchema.safeParse(input)
    if (!parsed.success) {
      const fields: Record<string, string[]> = {}
      for (const issue of parsed.error.issues) {
        const k = String(issue.path[0] ?? 'root')
        ;(fields[k] ??= []).push(issue.message)
      }
      throw new DomainError('validation_failed', 'Проверьте поля', fields)
    }
    const db = loadDB()
    const idx = db.trainers.findIndex((t) => t.id === id)
    if (idx < 0) throw new DomainError('not_found', 'Тренер не найден')
    const current = db.trainers[idx]!
    // Phone uniqueness check (excluding self)
    if (
      parsed.data.phone &&
      db.trainers.some((t) => t.id !== id && t.phone !== null && t.phone === parsed.data.phone)
    ) {
      throw new DomainError('validation_failed', 'Дубликат телефона', {
        phone: ['Тренер с таким телефоном уже существует'],
      })
    }
    const updated: Trainer = {
      ...current,
      fullName: parsed.data.fullName ?? current.fullName,
      phone: parsed.data.phone !== undefined ? (parsed.data.phone ?? null) : current.phone,
      isActive: parsed.data.isActive,
      updatedAt: new Date().toISOString(),
    }
    db.trainers[idx] = updated
    saveDB(db)
    return updated
  },

  async delete(id: TrainerId): Promise<void> {
    await delay()
    ensure('delete', 'trainers')
    const db = loadDB()
    const idx = db.trainers.findIndex((t) => t.id === id)
    if (idx < 0) throw new DomainError('not_found', 'Тренер не найден')
    db.trainers.splice(idx, 1)
    saveDB(db)
  },
}
