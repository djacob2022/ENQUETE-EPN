import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Accueil from "./pages/public/Accueil";
import Formulaire from "./pages/public/Formulaire";
import { Squelette } from "./ui";

// L'espace administrateur (graphiques compris) est chargé à part : le formulaire des EPN reste léger.
const Connexion = lazy(() => import("./pages/gestion/Connexion"));
const Gestion = lazy(() => import("./pages/gestion/Gestion"));

function Chargement() {
  return <div className="mx-auto max-w-5xl space-y-4 p-10"><Squelette className="h-10 w-64" /><Squelette className="h-64" /></div>;
}

export default function App() {
  return (
    <Suspense fallback={<Chargement />}>
      <Routes>
        <Route path="/" element={<Accueil />} />
        <Route path="/r/:jeton/*" element={<Formulaire />} />
        <Route path="/connexion" element={<Connexion />} />
        <Route path="/gestion/*" element={<Gestion />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
