# Run from PowerShell: .\scripts\windows-start.ps1 -Stage Setup
# Images, models and exports stay local. No publishing or cloud inference.
[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Data', 'Review', 'All')][string]$Stage = 'Setup',
    [string]$Model = 'qwen2.5vl:7b'
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot
try {
    function Invoke-Checked {
        param([string]$Program, [string[]]$Arguments)
        & $Program @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Command failed: $Program (exit $LASTEXITCODE)" }
    }
    $env:MPLCONFIGDIR = Join-Path $RepoRoot 'data\runtime\matplotlib'
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
    if ($Stage -in @('Setup', 'All')) {
        if (-not (Test-Path $Python)) {
            Invoke-Checked -Program 'py' -Arguments @('-3.12', '-m', 'venv', '.venv')
        }
        Invoke-Checked -Program $Python -Arguments @('-m', 'pip', 'install', '-e', '.[dev]')
        Invoke-Checked -Program $Python -Arguments @('-m', 'ruff', 'check', 'src', 'tests')
        Invoke-Checked -Program $Python -Arguments @('-m', 'mypy', '--strict', 'src')
        Invoke-Checked -Program $Python -Arguments @('-m', 'pytest', '-q')
        Invoke-Checked -Program '.\.venv\Scripts\archaeo.exe' -Arguments @('validate-config', 'configs/esselbach.yaml')
        Invoke-Checked -Program '.\.venv\Scripts\archaeo.exe' -Arguments @('demo')
    }
    if (-not (Test-Path $Python)) { throw 'Run -Stage Setup first (Python 3.12 required).' }
    $Cli = Join-Path $RepoRoot '.venv\Scripts\archaeo.exe'
    if ($Stage -in @('Data', 'All')) {
        Invoke-Checked -Program $Cli -Arguments @('fetch-dem', '--config', 'configs/esselbach.yaml')
        Invoke-Checked -Program $Cli -Arguments @('prepare-terrain', '--config', 'configs/esselbach.yaml')
        Write-Host 'Preview: exports\esselbach\terrain\overview.html'
    }
    if ($Stage -in @('Review', 'All')) {
        if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
            throw 'Install Ollama and download the vision model before -Stage Review.'
        }
        # Does not start/reconfigure an already-running service or download weights.
        # Start Ollama separately with OLLAMA_NO_CLOUD=1; see docs/Windows.md.
        Invoke-Checked -Program 'ollama' -Arguments @('show', $Model)
        Invoke-Checked -Program $Cli -Arguments @('review-batches', 'exports/esselbach/terrain/tiles',
            '--model', $Model, '--output', 'exports/esselbach/local-review')
        Write-Host 'Model suggestions are unvalidated. Human review required.'
    }
} finally {
    Pop-Location
}
