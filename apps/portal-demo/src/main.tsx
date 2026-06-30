import React from "react";
import { createRoot } from "react-dom/client";
import { PortalDemoApp } from "./PortalDemoApp";
import "@subpilot/portal-js/styles.css";
import "./portal-demo.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PortalDemoApp />
  </React.StrictMode>
);
