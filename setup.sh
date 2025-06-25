#!/bin/bash

# Script de configuração inicial do DIRIA
echo "🔧 Configuração Inicial do DIRIA"
echo "================================="

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado."
    echo "💡 Instale Python 3.8+ primeiro:"
    echo "   macOS: brew install python3"
    echo "   Ubuntu: sudo apt install python3 python3-venv"
    echo "   Windows: https://python.org/downloads/"
    exit 1
fi

echo "✅ Python encontrado: $(python3 --version)"

# Verificar se pip está instalado
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip não encontrado."
    echo "💡 Instale pip primeiro."
    exit 1
fi

echo "✅ pip encontrado: $(pip3 --version)"

# Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "🔄 Criando ambiente virtual..."
    python3 -m venv venv
    echo "✅ Ambiente virtual criado!"
else
    echo "✅ Ambiente virtual já existe!"
fi

# Ativar ambiente virtual
echo "🔄 Ativando ambiente virtual..."
source venv/bin/activate

# Atualizar pip
echo "📦 Atualizando pip..."
pip install --upgrade pip

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Criar arquivo .env se não existir
if [ ! -f ".env" ]; then
    echo "📝 Criando arquivo de configuração..."
    cp env_example.txt .env
    echo "✅ Arquivo .env criado!"
    echo "💡 Edite o arquivo .env se quiser usar APIs reais"
else
    echo "✅ Arquivo .env já existe!"
fi

# Migrar banco de dados
echo "🗄️  Configurando banco de dados..."
python migrate_db.py

# Testar sistema
echo "🧪 Testando sistema..."
python test_tokens.py

echo ""
echo "🎉 Configuração concluída!"
echo "=========================="
echo ""
echo "🚀 Para iniciar o sistema:"
echo "   ./start.sh"
echo ""
echo "🌐 Acesse: http://localhost:5001"
echo "👤 Login: admin@diria.com / admin123"
echo ""
echo "📚 Documentação:"
echo "   README.md - Documentação completa"
echo "   GUIA_RAPIDO.md - Guia de uso"
echo "   CONTROLE_TOKENS.md - Sistema de tokens"
echo ""
echo "🔧 Configuração de APIs (opcional):"
echo "   Edite o arquivo .env e adicione suas chaves de API"
echo ""
echo "✅ Sistema pronto para uso!" 