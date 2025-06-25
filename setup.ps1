# Script de configuração inicial do DIRIA para Windows (PowerShell)
Write-Host "🔧 Configuração Inicial do DIRIA" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Verificar se Python está instalado
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python encontrado: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python não encontrado." -ForegroundColor Red
    Write-Host "💡 Instale Python 3.8+ primeiro:" -ForegroundColor Yellow
    Write-Host "   https://python.org/downloads/" -ForegroundColor Cyan
    exit 1
}

# Verificar se pip está instalado
try {
    $pipVersion = pip --version 2>&1
    Write-Host "✅ pip encontrado: $pipVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ pip não encontrado." -ForegroundColor Red
    Write-Host "💡 Instale pip primeiro." -ForegroundColor Yellow
    exit 1
}

# Criar ambiente virtual se não existir
if (-not (Test-Path "venv")) {
    Write-Host "🔄 Criando ambiente virtual..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "✅ Ambiente virtual criado!" -ForegroundColor Green
} else {
    Write-Host "✅ Ambiente virtual já existe!" -ForegroundColor Green
}

# Ativar ambiente virtual
Write-Host "🔄 Ativando ambiente virtual..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"

# Atualizar pip
Write-Host "📦 Atualizando pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# Instalar dependências
Write-Host "📦 Instalando dependências..." -ForegroundColor Cyan
pip install -r requirements.txt

# Criar arquivo .env se não existir
if (-not (Test-Path ".env")) {
    Write-Host "📝 Criando arquivo de configuração..." -ForegroundColor Cyan
    Copy-Item "env_example.txt" ".env"
    Write-Host "✅ Arquivo .env criado!" -ForegroundColor Green
    Write-Host "💡 Edite o arquivo .env se quiser usar APIs reais" -ForegroundColor Yellow
} else {
    Write-Host "✅ Arquivo .env já existe!" -ForegroundColor Green
}

# Migrar banco de dados
Write-Host "🗄️  Configurando banco de dados..." -ForegroundColor Cyan
python migrate_db.py

# Testar sistema
Write-Host "🧪 Testando sistema..." -ForegroundColor Cyan
python test_tokens.py

Write-Host ""
Write-Host "🎉 Configuração concluída!" -ForegroundColor Green
Write-Host "==========================" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Para iniciar o sistema:" -ForegroundColor Cyan
Write-Host "   .\start.ps1" -ForegroundColor White
Write-Host ""
Write-Host "🌐 Acesse: http://localhost:5001" -ForegroundColor Cyan
Write-Host "👤 Login: admin@diria.com / admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "📚 Documentação:" -ForegroundColor Yellow
Write-Host "   README.md - Documentação completa" -ForegroundColor White
Write-Host "   GUIA_RAPIDO.md - Guia de uso" -ForegroundColor White
Write-Host "   CONTROLE_TOKENS.md - Sistema de tokens" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Configuração de APIs (opcional):" -ForegroundColor Yellow
Write-Host "   Edite o arquivo .env e adicione suas chaves de API" -ForegroundColor White
Write-Host ""
Write-Host "✅ Sistema pronto para uso!" -ForegroundColor Green 