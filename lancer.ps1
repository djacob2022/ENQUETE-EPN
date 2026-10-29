# Lance ENQUETE-EPN en local avec Docker (Windows, PowerShell).
# Usage : .\lancer.ps1            demarre (et construit au premier lancement)
#         .\lancer.ps1 arreter    arrete les conteneurs (les donnees sont conservees)
#         .\lancer.ps1 effacer    arrete et SUPPRIME toutes les donnees (base, fichiers)
param([string]$action = "demarrer")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Docker n'est pas demarre. Lancez Docker Desktop puis relancez ce script." -ForegroundColor Red; exit 1 }

if ($action -eq "arreter") { docker compose stop; exit }
if ($action -eq "effacer") { docker compose down -v; exit }

function Aleatoire([int]$n) { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $n | ForEach-Object { [char]$_ }) }

if (-not (Test-Path .env)) {
  $mdpAdmin = Aleatoire 14
  (Get-Content -Encoding UTF8 .env.example) `
    -replace '^DJANGO_SECRET_KEY=.*', "DJANGO_SECRET_KEY=$(Aleatoire 50)" `
    -replace '^DJANGO_SUPERUSER_PASSWORD=.*', "DJANGO_SUPERUSER_PASSWORD=$mdpAdmin" `
    -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(Aleatoire 24)" |
    Set-Content -Encoding utf8 .env
  Write-Host "Fichier .env cree. Identifiants administrateur : admin / $mdpAdmin (notez-les)." -ForegroundColor Green
}

docker compose up -d --build
Write-Host ""
Write-Host "Patientez une vingtaine de secondes au premier lancement, puis ouvrez :"
Write-Host "  Espace administrateur : http://localhost:8000/connexion/  (identifiants dans .env)"
Write-Host "  E-mails envoyes (test) : http://localhost:8025"
Write-Host "Journal de l'application : docker compose logs -f web"
