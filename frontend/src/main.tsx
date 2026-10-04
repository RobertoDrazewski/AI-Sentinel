import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { AppModeProvider } from "./context/AppModeContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppModeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </AppModeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
