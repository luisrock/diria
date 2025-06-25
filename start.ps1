# Liberar porta 5001 se estiver ocupada
$port = 5001
$procs = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($procs) {
    Write-Host "⚠️  Encontrado processo na porta $port. Finalizando..." -ForegroundColor Yellow
    foreach ($pid in $procs) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Write-Host "✅ Porta $port liberada!" -ForegroundColor Green
}

# Script de inicialização do DIRIA para Windows (PowerShell)
Write-Host "🚀 Iniciando DIRIA - Sistema de Minutas Judiciais" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# Verificar se o ambiente virtual está ativo
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠️  Ambiente virtual não detectado." -ForegroundColor Yellow
    
    # Verificar se o ambiente virtual existe
    if (Test-Path "venv") {
        Write-Host "🔄 Ativando ambiente virtual..." -ForegroundColor Cyan
        & "venv\Scripts\Activate.ps1"
        Write-Host "✅ Ambiente virtual ativado!" -ForegroundColor Green
    } else {
        Write-Host "❌ Ambiente virtual não encontrado." -ForegroundColor Red
        Write-Host "💡 Criando ambiente virtual..." -ForegroundColor Cyan
        python -m venv venv
        & "venv\Scripts\Activate.ps1"
        Write-Host "✅ Ambiente virtual criado e ativado!" -ForegroundColor Green
        
        Write-Host "📦 Instalando dependências..." -ForegroundColor Cyan
        pip install -r requirements.txt
        Write-Host "✅ Dependências instaladas!" -ForegroundColor Green
    }
} else {
    Write-Host "✅ Ambiente virtual já está ativo!" -ForegroundColor Green
}

# Verificar se as dependências estão instaladas
Write-Host "📦 Verificando dependências..." -ForegroundColor Cyan
try {
    python -c "import flask, openai, anthropic, google.generativeai, tiktoken" 2>$null
} catch {
    Write-Host "❌ Dependências não encontradas." -ForegroundColor Red
    Write-Host "💡 Instalando dependências..." -ForegroundColor Cyan
    pip install -r requirements.txt
    Write-Host "✅ Dependências instaladas!" -ForegroundColor Green
}

# Verificar se o banco de dados existe
if (-not (Test-Path "instance\diria.db")) {
    Write-Host "🗄️  Banco de dados não encontrado. Criando..." -ForegroundColor Cyan
    python migrate_db.py
}

# Testar o sistema de tokens
Write-Host "🧪 Testando sistema de tokens..." -ForegroundColor Cyan
python test_tokens.py

Write-Host ""
Write-Host "✅ Sistema pronto!" -ForegroundColor Green
Write-Host "🌐 Acesse: http://localhost:5001" -ForegroundColor Cyan
Write-Host "👤 Login: admin@diria.com / admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Funcionalidades disponíveis:" -ForegroundColor Yellow
Write-Host "   • Geração de minutas com IA" -ForegroundColor White
Write-Host "   • Controle de tokens em tempo real" -ForegroundColor White
Write-Host "   • Painel administrativo" -ForegroundColor White
Write-Host "   • Logs e estatísticas" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Para parar: Ctrl+C" -ForegroundColor Red
Write-Host ""

# Iniciar a aplicação
python app.py 