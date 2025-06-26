#!/bin/bash

# DIRIA - Script de Deploy Otimizado para Quick Deploy
# Repo: https://github.com/luisrock/diria
# Site: diria.com.br
# Python: 3.11.13

echo "🚀 Iniciando deploy automático do DIRIA..."

# Definir variáveis
SITE_DIR="/home/forge/diria.com.br"
PYTHON_VERSION="python3.11"
REPO_URL="https://github.com/luisrock/diria.git"

# Ir para o diretório do site
cd "$SITE_DIR"

# Verificar se é a primeira vez (se não existe .git)
if [ ! -d ".git" ]; then
    echo "📥 Primeira execução - clonando repositório..."
    git clone "$REPO_URL" .
else
    echo "🔄 Atualizando código do GitHub..."
    git fetch origin
    git reset --hard origin/main
fi

echo "✅ Código atualizado com sucesso"

# Preservar arquivos de configuração existentes
echo "📁 Preservando configurações..."

# Backup do .env se existir (mantido para fallback)
if [ -f ".env" ]; then
    echo "💾 Backup do .env preservado"
else
    echo "📝 Criando .env padrão..."
    cat > .env << 'EOF'
# DIRIA - Configurações do Sistema
FLASK_SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///diria.db

# Configurações OpenAI (fallback - preferencialmente use o painel admin)
OPENAI_API_KEY=your-openai-key-here

# Configurações Anthropic (fallback - preferencialmente use o painel admin)
ANTHROPIC_API_KEY=your-anthropic-key-here

# Configurações Google (fallback - preferencialmente use o painel admin)
GOOGLE_API_KEY=your-google-key-here

# Configurações do Sistema
DEBUG=False
HOST=0.0.0.0
PORT=8000
EOF
    echo "⚠️  IMPORTANTE: Configure as chaves de API via painel administrativo!"
fi

# Criar/atualizar gunicorn.conf.py
echo "⚙️ Configurando Gunicorn..."
cat > gunicorn.conf.py << 'EOF'
# Gunicorn configuration for DIRIA
bind = "127.0.0.1:8000"
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True

# Logs
accesslog = "/home/forge/diria.com.br/logs/access.log"
errorlog = "/home/forge/diria.com.br/logs/error.log"
loglevel = "info"
EOF

# Configurar ambiente Python
echo "🐍 Configurando ambiente Python..."
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    $PYTHON_VERSION -m venv venv
fi

source venv/bin/activate

# Atualizar pip
echo "📦 Atualizando pip..."
python -m pip install --upgrade pip

# Instalar/atualizar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Criar diretório de logs
echo "📁 Criando diretório de logs..."
mkdir -p logs

# Configurar banco de dados
echo "🗄️ Configurando banco de dados..."

# Verificar se o banco existe
if [ ! -f "instance/diria.db" ]; then
    echo "🆕 Banco de dados não encontrado - criando do zero..."
    
    # Criar todas as tabelas
    echo "📋 Criando estrutura do banco..."
    python -c "from app import app, db; app.app_context().push(); db.create_all(); print('✅ Tabelas criadas com sucesso!')"
    
    # Inicializar com dados padrão
    echo "📝 Inicializando com dados padrão..."
    python -c "from app import init_db; init_db(); print('✅ Dados padrão criados!')"
    
    # Executar migração das instruções
    echo "🔄 Executando migração das instruções..."
    python migrate_instructions.py
    
    echo "✅ Banco de dados inicializado completamente!"
else
    echo "🔄 Banco existente - executando migrações..."
    
    # Executar migração de tokens
    python migrate_db.py
    
    # Executar migração das instruções
    python migrate_instructions.py
    
    # Executar migração das chaves de API (se existir)
    if [ -f "migrate_api_keys.py" ]; then
        echo "🔑 Executando migração das chaves de API..."
        python migrate_api_keys.py
    else
        echo "ℹ️  Script de migração de chaves não encontrado"
    fi
    
    echo "✅ Migrações concluídas!"
fi

# Configurar permissões (opcional)
echo "🔐 Configurando permissões..."
chmod +x start.sh 2>/dev/null || true

# Reiniciar a aplicação usando supervisorctl
echo "🔄 Reiniciando aplicação..."

# Tentar diferentes métodos para reiniciar a aplicação
RESTART_SUCCESS=false

# Método 1: Tentar supervisorctl sem sudo
if command -v supervisorctl >/dev/null 2>&1; then
    echo "🔄 Tentando reiniciar via supervisorctl..."
    if supervisorctl restart diria 2>/dev/null; then
        echo "✅ Aplicação reiniciada via supervisorctl"
        RESTART_SUCCESS=true
    else
        echo "⚠️  supervisorctl sem sudo falhou"
    fi
fi

# Método 2: Tentar com sudo se o primeiro falhou
if [ "$RESTART_SUCCESS" = false ] && command -v sudo >/dev/null 2>&1; then
    echo "🔄 Tentando reiniciar via sudo supervisorctl..."
    if sudo supervisorctl restart diria 2>/dev/null; then
        echo "✅ Aplicação reiniciada via sudo supervisorctl"
        RESTART_SUCCESS=true
    else
        echo "⚠️  sudo supervisorctl falhou"
    fi
fi

# Método 3: Tentar parar e iniciar manualmente
if [ "$RESTART_SUCCESS" = false ]; then
    echo "🔄 Tentando reiniciar manualmente..."
    
    # Parar processo se estiver rodando
    pkill -f "gunicorn.*diria" 2>/dev/null || true
    sleep 2
    
    # Iniciar novamente
    if [ -f "venv/bin/gunicorn" ]; then
        nohup venv/bin/gunicorn -c gunicorn.conf.py app:app > logs/gunicorn.log 2>&1 &
        echo "✅ Aplicação reiniciada manualmente"
        RESTART_SUCCESS=true
    else
        echo "❌ Gunicorn não encontrado no ambiente virtual"
    fi
fi

if [ "$RESTART_SUCCESS" = false ]; then
    echo "❌ Não foi possível reiniciar a aplicação automaticamente"
    echo "💡 Execute manualmente: sudo supervisorctl restart diria"
fi

# Verificar status da aplicação
echo "📊 Verificando status da aplicação..."
sleep 5

# Tentar verificar status
if command -v supervisorctl >/dev/null 2>&1; then
    if supervisorctl status diria 2>/dev/null; then
        echo "✅ Status verificado via supervisorctl"
    elif sudo supervisorctl status diria 2>/dev/null; then
        echo "✅ Status verificado via sudo supervisorctl"
    else
        echo "⚠️  Não foi possível verificar status via supervisorctl"
    fi
else
    echo "ℹ️  supervisorctl não encontrado"
fi

# Verificar se a aplicação está funcionando
echo "🧪 Testando aplicação..."
sleep 3

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 2>/dev/null | grep -q "302\|200"; then
    echo "✅ Aplicação respondendo corretamente!"
else
    echo "⚠️  Aplicação pode não estar respondendo - verifique os logs"
    echo "💡 Logs disponíveis em: logs/error.log e logs/access.log"
fi

echo ""
echo "🎉 Deploy automático concluído com sucesso!"
echo "🌐 Aplicação disponível em: https://diria.com.br"
echo ""
echo "👤 Usuários padrão criados:"
echo "   • admin@diria.com / admin123 (Administrador)"
echo "   • assessor1@diria.com / senha123 (Assessor 1)"
echo "   • assessor2@diria.com / senha456 (Assessor 2)"
echo ""
echo "🔑 IMPORTANTE: Configure as chaves de API via painel administrativo!"
echo "   Acesse: https://diria.com.br/admin/api_keys"
echo "   Ou use o arquivo .env como fallback"
echo ""
echo "📋 Próximos passos:"
echo "   1. Acesse o painel admin: https://diria.com.br/admin"
echo "   2. Vá em 'Gerenciar Chaves de API'"
echo "   3. Configure as chaves de OpenAI, Anthropic e Google"
echo "   4. Teste a geração de minutas" 