param(
    [Parameter(Mandatory=$true)][ValidateSet('batch-submit','batch-collect','full-step','full-run')][string]$Command,
    [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference = 'Stop'
$qaPointer = [IntPtr]::Zero
try {
    $qaSecret = Import-Clixml -LiteralPath (Join-Path $env:LOCALAPPDATA 'IndexedIconPack\openai-api-key.xml')
    if ($qaSecret -isnot [SecureString]) { throw 'Credential is not a SecureString' }
    $qaPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($qaSecret)
    $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($qaPointer)
    Push-Location -LiteralPath (Join-Path $PSScriptRoot '..')
    try {
        if ($Command -in @('full-step','full-run')) {
            $qaFullCommand = if ($Command -eq 'full-run') { 'run' } else { 'step' }
            & uv.exe run --no-project --with openai==3.26.1 --with-requirements requirements-build.txt python -B tools/full_alternative_batch.py $qaFullCommand --output $Output
        } else {
            & uv.exe run --no-project --with openai==3.26.1 --with-requirements requirements-build.txt python -B tools/automated_search_qa.py $Command --output $Output
        }
        $qaExitCode = $LASTEXITCODE
    } finally { Pop-Location }
} finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    if ($qaPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($qaPointer) }
}
exit $qaExitCode
