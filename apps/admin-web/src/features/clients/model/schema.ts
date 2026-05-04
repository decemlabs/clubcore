// Schemas live in src/entities/client/schema.ts so mock services can validate
// the same shape the form submits without crossing the features → shared boundary in reverse.
export {
  clientCreateSchema,
  clientUpdateSchema,
  clientsListQuerySchema,
  type ClientCreateFormInput,
  type ClientUpdateFormInput,
  type ClientsListQueryInput,
} from '@/entities/client/schema'
