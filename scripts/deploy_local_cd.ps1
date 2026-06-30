param(
    [string]$GhcrOwner = $(if ($env:GHCR_OWNER) { $env:GHCR_OWNER } else { "peaceful-fptu-k16" }),
    [string]$ImageTag = $(if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "latest" }),
    [string]$FastApiUrl = $(if ($env:FASTAPI_HEALTH_URL) { $env:FASTAPI_HEALTH_URL } else { "http://localhost:8000/health" }),
    [switch]$SkipHealthCheck
)

$ErrorActionPreference = "Stop"

$env:GHCR_OWNER = $GhcrOwner.ToLowerInvariant()
$env:IMAGE_TAG = $ImageTag

$composeFiles = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.ghcr.yml"
)

Write-Host "Deploying GHCR images:"
Write-Host "  ghcr.io/$($env:GHCR_OWNER)/final-ddm501-fastapi:$($env:IMAGE_TAG)"
Write-Host "  ghcr.io/$($env:GHCR_OWNER)/final-ddm501-streamlit:$($env:IMAGE_TAG)"

docker compose @composeFiles pull fastapi streamlit
docker compose @composeFiles up -d --no-deps --no-build fastapi streamlit

if (-not $SkipHealthCheck) {
    Write-Host "Waiting for FastAPI health check: $FastApiUrl"
    $ready = $false
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            Invoke-RestMethod -Uri $FastApiUrl -TimeoutSec 5 | Out-Null
            $ready = $true
            break
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }

    if (-not $ready) {
        docker compose @composeFiles ps fastapi streamlit
        throw "FastAPI health check failed after deployment."
    }
}

docker compose @composeFiles ps fastapi streamlit
Write-Host "Local CD deploy completed."
