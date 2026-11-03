import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { FournisseurToast } from "./ui";
import "./index.css";

const client = new QueryClient({
  defaultOptions: {
    queries: { retry: (n, e: any) => n < 2 && ![401, 403, 404].includes(e?.statut), refetchOnWindowFocus: false, staleTime: 15_000 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <FournisseurToast>
          <App />
        </FournisseurToast>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
