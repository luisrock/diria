#!/bin/bash

# Liberar porta 5001 se estiver ocupada
if lsof -ti:5001 &>/dev/null; then
    echo "⚠️  Encontrado processo na porta 5001. Finalizando..."
    lsof -ti:5001 | xargs kill -9
    echo "✅ Porta 5001 liberada!"
fi

# Script de inicialização do DIRIA
echo "🚀 Iniciando DIRIA - Sistema de Minutas Judiciais"
echo "=================================================="

# Verificar se o ambiente virtual está ativo
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Ambiente virtual não detectado."
    
    # Verificar se o ambiente virtual existe
    if [ -d "venv" ]; then
        echo "🔄 Ativando ambiente virtual..."
        source venv/bin/activate
        echo "✅ Ambiente virtual ativado!"
    else
        echo "❌ Ambiente virtual não encontrado."
        echo "💡 Criando ambiente virtual..."
        python3 -m venv venv
        source venv/bin/activate
        echo "✅ Ambiente virtual criado e ativado!"
        
        echo "📦 Instalando dependências..."
        pip install -r requirements.txt
        echo "✅ Dependências instaladas!"
    fi
else
    echo "✅ Ambiente virtual já está ativo!"
fi

# Verificar se as dependências estão instaladas
echo "📦 Verificando dependências..."
if ! python -c "import flask, openai, anthropic, google.generativeai, tiktoken" 2>/dev/null; then
    echo "❌ Dependências não encontradas."
    echo "💡 Instalando dependências..."
    pip install -r requirements.txt
    echo "✅ Dependências instaladas!"
fi

# Verificar se o banco de dados existe
if [ ! -f "instance/diria.db" ]; then
    echo "🗄️  Banco de dados não encontrado. Criando..."
    python migrate_db.py
fi

# Testar o sistema de tokens
echo "🧪 Testando sistema de tokens..."
python test_tokens.py

echo ""
echo "✅ Sistema pronto!"
echo "🌐 Acesse: http://localhost:5001"
echo "👤 Login: admin@diria.com / admin123"
echo ""
echo "📊 Funcionalidades disponíveis:"
echo "   • Geração de minutas com IA"
echo "   • Controle de tokens em tempo real"
echo "   • Painel administrativo"
echo "   • Logs e estatísticas"
echo ""
echo "🛑 Para parar: Ctrl+C"
echo ""

# Iniciar a aplicação
python app.py 