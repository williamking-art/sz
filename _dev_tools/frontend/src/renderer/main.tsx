import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { GameStoreProvider } from "./store/gameStore";
import "./styles/theme.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <GameStoreProvider>
      <App />
    </GameStoreProvider>
  </React.StrictMode>
);