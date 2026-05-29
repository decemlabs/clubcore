import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App.jsx';
import { TweaksProvider } from './context/TweaksContext.jsx';
import { UIProvider } from './context/UIContext.jsx';
import { registerPwa } from './services/pwa.js';

registerPwa();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <TweaksProvider>
        <UIProvider>
          <App />
        </UIProvider>
      </TweaksProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
