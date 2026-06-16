import { QueryClientProvider } from '@tanstack/react-query';
import { Tooltip as TooltipPrimitive } from 'radix-ui';
import type { ReactNode } from 'react';
import { queryClient } from '@/api/query-client';
import { ModalsProvider } from '@/components/modals/ModalsProvider';

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipPrimitive.Provider delayDuration={200}>
        <ModalsProvider>{children}</ModalsProvider>
      </TooltipPrimitive.Provider>
    </QueryClientProvider>
  );
}
