# =============================================================================
# Antigravity Swarm — Project Bootstrapper
# Usage: .\bootstrap.ps1 -ProjectName "my-app" -Destination "C:\projects\my-app"
#
# This script:
#   1. Creates a new project workspace with Manus Protocol shared memory files
#   2. Copies the Swarm agent scripts into the project
#   3. Copies the AGENT_CONTEXT.md template so you can brief the agents
# =============================================================================
param (
    [Parameter(Mandatory=$true)]
    [string]$ProjectName,

    [Parameter(Mandatory=$false)]
    [string]$Destination = ".\$ProjectName"
)

$SWARM_SOURCE = "C:\Users\sean\.gemini\skills\antigravity-swarm"
$TARGET = $Destination

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Antigravity Swarm Bootstrap" -ForegroundColor Cyan
Write-Host "  Project: $ProjectName" -ForegroundColor Cyan
Write-Host "  Target:  $TARGET" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Create project directory
if (Test-Path $TARGET) {
    Write-Host "[WARN] Directory already exists: $TARGET" -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $TARGET -Force | Out-Null
    Write-Host "[OK] Created project directory: $TARGET" -ForegroundColor Green
}

# 2. Copy the Swarm engine
$swarmDest = Join-Path $TARGET ".swarm"
New-Item -ItemType Directory -Path $swarmDest -Force | Out-Null
Copy-Item -Path "$SWARM_SOURCE\scripts\*" -Destination $swarmDest -Recurse -Force
Write-Host "[OK] Copied Swarm engine to: $swarmDest" -ForegroundColor Green

# 3. Copy documentation
Copy-Item "$SWARM_SOURCE\FRAMEWORK_GUIDE.md" -Destination $TARGET -Force
Copy-Item "$SWARM_SOURCE\ARCHITECTURE.md" -Destination $TARGET -Force
Write-Host "[OK] Copied framework documentation" -ForegroundColor Green

# 4. Initialize Manus Protocol shared memory files
$taskPlan = Join-Path $TARGET "task_plan.md"
$findings = Join-Path $TARGET "findings.md"
$progress = Join-Path $TARGET "progress.md"

Set-Content -Path $taskPlan -Value @"
# Task Plan: $ProjectName

## Mission
> [Fill in your mission description here]

## Checklist
- [ ] Review AGENT_CONTEXT.md and ensure it is filled out
- [ ] Planner generates subagents.yaml
- [ ] Swarm executes mission
"@

Set-Content -Path $findings -Value @"
# Findings & Shared Scratchpad: $ProjectName

This file is the shared memory for all Swarm agents.
Agents READ this before acting and WRITE discoveries here.

## Project Context
> [Agents will populate this from AGENT_CONTEXT.md]

## Architecture Decisions
> [Oracle will write ADRs here]

## File Map
> [Explore will write the codebase map here]

## Risk Register
> [Momus will write risks here]
"@

Set-Content -Path $progress -Value @"
# Mission Progress: $ProjectName

## Status Log
- [ ] Bootstrap complete — awaiting mission start
"@

Write-Host "[OK] Initialized Manus Protocol files (task_plan.md, findings.md, progress.md)" -ForegroundColor Green

# 5. Copy the AGENT_CONTEXT.md briefing template
Copy-Item "$SWARM_SOURCE\AGENT_CONTEXT.md" -Destination $TARGET -Force
Write-Host "[OK] Copied AGENT_CONTEXT.md — fill this in before running the Swarm!" -ForegroundColor Yellow

# 6. Copy swarm_config.json from user profile
$swarmConfig = "C:\Users\sean\.gemini\antigravity\swarm_config.json"
if (Test-Path $swarmConfig) {
    Copy-Item $swarmConfig -Destination $TARGET -Force
    Write-Host "[OK] Copied swarm_config.json (current mode: $(((Get-Content $swarmConfig | ConvertFrom-Json).mode)))" -ForegroundColor Green
} else {
    Write-Host "[WARN] swarm_config.json not found — create it manually." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Bootstrap Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. cd '$TARGET'" -ForegroundColor White
Write-Host "  2. Fill in AGENT_CONTEXT.md with your project details" -ForegroundColor White
Write-Host "  3. Run: python .swarm\planner.py ""Your mission description""" -ForegroundColor White
Write-Host "  4. Run: python .swarm\orchestrator.py" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
