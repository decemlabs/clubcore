/**
 * Service contracts. Transport-agnostic — mock and http implementations
 * both satisfy these interfaces.
 */
export type {
  AuthService,
  MeResponse,
  EmailLoginInput,
  TelegramStartResponse,
  TelegramStatusResponse,
  TelegramVerifyInput,
} from './auth'
export type {
  ClientsService,
  ClientsListQuery,
  ClientCreateInput,
  ClientUpdateInput,
  Client,
  ClientId,
  Pagination,
} from './clients'
export { emailLoginSchema, telegramOtpSchema } from './authSchema'
export type { EmailLoginFormInput, TelegramOtpFormInput } from './authSchema'
export type {
  MembershipsService,
  MembershipsListQuery,
  MembershipPlansListQuery,
  MembershipCreateInput,
  MembershipPlanCreateInput,
  MembershipPlanUpdateInput,
} from './memberships'
export type {
  VisitsService,
  VisitsListQuery,
  GymMeta,
} from './visits'
