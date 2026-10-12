$ErrorActionPreference = 'Stop'
$packageRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$run = Join-Path $packageRoot 'work\full-annotation-gpt6-sol-high-v1'
$keyPath = Join-Path $env:LOCALAPPDATA 'IndexedIconPack\openai-api-key.xml'
$log = Join-Path $run 'runner.log'
$outcome = Join-Path $run 'runner-outcome.json'
$status = 'failed'
$message = $null
$pointer = [IntPtr]::Zero
@{ status = 'running'; started_at_utc = [DateTime]::UtcNow.ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $outcome -Encoding UTF8
try {
    $secure = Import-Clixml -LiteralPath $keyPath
    if ($secure -isnot [SecureString]) { throw 'Credential file is not a SecureString' }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    Push-Location -LiteralPath $packageRoot
    try {
        & uv run --with openai==3.26.1 --with Pillow==12.3.0 python -B tools/full_annotation_batch.py run --run $run --poll-seconds 60 *>> $log
        if ($LASTEXITCODE -ne 0) { throw "Full annotation runner exited with code $LASTEXITCODE; see runner.log" }
    } finally {
        Pop-Location
    }
    $status = 'completed'
} catch {
    $message = $_.Exception.Message
    Add-Content -LiteralPath $log -Value "runner error: $message"
} finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    @{ status = $status; message = $message; finished_at_utc = [DateTime]::UtcNow.ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath $outcome -Encoding UTF8
}
if ($status -ne 'completed') { exit 2 }
