import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authKeys } from './keys'
import { services } from '@/shared/api/services'
import type { EmailLoginInput, MeResponse, TelegramVerifyInput } from '@/shared/api/contracts/auth'

export function useMe() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: () => services.auth.me(),
    retry: false,
    staleTime: 30_000,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: EmailLoginInput) => services.auth.login(input),
    onSuccess: (me) => {
      qc.setQueryData<MeResponse>(authKeys.me, me)
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => services.auth.logout(),
    onSuccess: () => {
      qc.clear()
    },
  })
}

export function useTelegramStart() {
  return useMutation({
    mutationFn: () => services.auth.telegramStart(),
  })
}

export function useTelegramStatus(token: string | null, enabled: boolean) {
  return useQuery({
    queryKey: token ? authKeys.telegramStatus(token) : ['auth', 'telegram-status', 'idle'],
    queryFn: () => services.auth.telegramStatus(token!),
    enabled: !!token && enabled,
    refetchInterval: 3000,
    retry: false,
  })
}

export function useTelegramVerify() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: TelegramVerifyInput) => services.auth.telegramVerify(input),
    onSuccess: (me) => {
      qc.setQueryData<MeResponse>(authKeys.me, me)
    },
  })
}
