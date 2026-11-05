import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AccesFormulaire from "./pages/public/AccesFormulaire";
import Formulaire from "./pages/public/Formulaire";
import { Squelette } from "./ui";

// L'espace administrateur (graphiques compris) est chargé à part : le formulaire des EPN reste léger.
const Connexion = lazy(() => import("./pages/gestion/Connexion"));
const Gestion = lazy(() => import("./pages/gestion/Gestion"));
const MotDePasse = lazy(() => import("./pages/gestion/MotDePasse"));
const Aide = lazy(() => import("./pages/public/Aide"));

function Chargement() {
  return <div className="mx-auto max-w-5xl space-y-4 p-10"><Squelette className="h-10 w-64" /><Squelette className="h-64" /></div>;
}

export default function App() {
  return (
    <Suspense fallback={<Chargement />}>
      <Routes>
        <Route path="/" element={<AccesFormulaire />} />
        <Route path="/formulaire" element={<AccesFormulaire />} />
        <Route path="/r/:jeton/*" element={<Formulaire />} />
        <Route path="/connexion" element={<Connexion />} />
        <Route path="/mot-de-passe-oublie" element={<MotDePasse />} />
        <Route path="/mot-de-passe/:uid/:jeton" element={<MotDePasse />} />
        <Route path="/aide" element={<Aide />} />
        <Route path="/gestion/*" element={<Gestion />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
