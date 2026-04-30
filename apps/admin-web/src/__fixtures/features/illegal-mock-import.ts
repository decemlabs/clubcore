// FIXTURE: must trigger `import/no-restricted-paths`.
import { services as mockServices } from '@/shared/api/services/mock'
import { services as httpServices } from '@/shared/api/services/http'

export const illegal = { mockServices, httpServices }
