// Applique le thème sombre avant l'affichage, pour éviter un flash clair (fichier séparé : la CSP interdit les scripts en ligne).
try { if (localStorage.getItem("theme") === "sombre") document.documentElement.classList.add("dark"); } catch (e) { /* stockage indisponible */ }
