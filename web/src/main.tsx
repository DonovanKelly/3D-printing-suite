/** Mount the workbench with locally bundled fonts and assets. */
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);

// Registration caches application assets only; imported artwork stays in worker memory.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(new URL(/* @vite-ignore */ "../sw.js", import.meta.url))
      .catch((error) => console.warn("Offline cache unavailable", error));
  });
}
