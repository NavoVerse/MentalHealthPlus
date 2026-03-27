import React from 'react';
import { createRoot } from 'react-dom/client';

function App() {
  return null;
}

const container = document.getElementById('root');
const root = createRoot(container);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
