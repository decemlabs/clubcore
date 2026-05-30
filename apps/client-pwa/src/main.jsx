import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';

import App from './App.jsx';
import { queryClient } from './lib/queryClient.ts';
import { AuthProvider } from './context/AuthContext.jsx';
import { TweaksProvider } from './context/TweaksContext.jsx';
import { UIProvider } from './context/UIContext.jsx';
import { registerPwa } from './services/pwa.js';

registerPwa();

// Provider order (Plan 71-07):
//   BrowserRouter → QueryClientProvider → AuthProvider → TweaksProvider → UIProvider → App
//
// QueryClientProvider must be above AuthProvider (AuthProvider uses useQuery).
// AuthProvider must be above App (App uses useAuth() via RequireAuth).
// BrowserRouter must wrap everything (RequireAuth inside App uses useNavigate/Navigate).
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TweaksProvider>
            <UIProvider>
              <App />
            </UIProvider>
          </TweaksProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
