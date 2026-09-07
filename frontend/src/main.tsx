import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

// Opt into React Router v7 behaviours now so the console stays clean and the
// upgrade is a one-line change later.
const routerFuture = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter future={routerFuture}>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
