# Lance ENQUETE-EPN en local avec Docker (Windows, PowerShell).
# Usage : .\lancer.ps1            demarre (et construit au premier lancement)
#         .\lancer.ps1 arreter    arrete les conteneurs (les donnees sont conservees)
#         .\lancer.ps1 effacer    arrete et SUPPRIME toutes les donnees (base, fichiers)
param([string]$action = "demarrer")
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker n'est pas installe. Installez Docker Desktop : https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
  exit 1
}
# Verification via cmd : sous Windows PowerShell 5.1, une erreur ecrite par docker sur stderr
# interromprait le script au lieu d'afficher le message ci-dessous.
cmd /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker Desktop n'est pas demarre (ou pas encore pret)." -ForegroundColor Red
  Write-Host "Ouvrez Docker Desktop, attendez l'indication 'Engine running' en bas a gauche, puis relancez ce script."
  exit 1
}
$ErrorActionPreference = "Stop"

if ($action -eq "arreter") { docker compose --profile dev stop; exit }
if ($action -eq "effacer") { docker compose --profile dev down -v; exit }

function Aleatoire([int]$n) { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $n | ForEach-Object { [char]$_ }) }

if (-not (Test-Path .env)) {
  $mdpAdmin = Aleatoire 14
  (Get-Content -Encoding UTF8 .env.example) `
    -replace '^DJANGO_SECRET_KEY=.*', "DJANGO_SECRET_KEY=$(Aleatoire 50)" `
    -replace '^DJANGO_SUPERUSER_PASSWORD=.*', "DJANGO_SUPERUSER_PASSWORD=$mdpAdmin" `
    -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(Aleatoire 24)" `
    -replace '^COOKIES_SECURE=.*', 'COOKIES_SECURE=0' `
    -replace '^CHARGER_DONNEES_DEMO=.*', 'CHARGER_DONNEES_DEMO=1' |
    Set-Content -Encoding utf8 .env
  Write-Host "Fichier .env cree. Identifiants administrateur : admin / $mdpAdmin (notez-les)." -ForegroundColor Green
}

docker compose --profile dev up -d --build
Write-Host ""
Write-Host "Patientez une vingtaine de secondes au premier lancement, puis ouvrez :"
Write-Host "  Espace administrateur : http://localhost:8000/connexion/  (identifiants dans .env)"
Write-Host "  E-mails envoyes (test) : http://localhost:8025"
Write-Host "Journal de l'application : docker compose logs -f web"
