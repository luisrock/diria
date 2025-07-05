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
timeout = 300
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
    
    # Executar migração consolidada
    echo "🔄 Executando migração consolidada..."
    python migrate_db.py
    
    # Migrar modelos hardcoded para o banco de dados (sempre na primeira execução)
    echo "🤖 Migrando modelos de IA para o banco de dados..."
    python migrate_models_to_db.py
    
    # Limpar tabelas desnecessárias (sempre na primeira execução)
    echo "🧹 Limpando tabelas desnecessárias..."
    python cleanup_db.py
    
    echo "✅ Banco de dados inicializado completamente!"
else
    echo "🔄 Banco existente - executando backup e migração..."
    
    # CRIAR BACKUP AUTOMÁTICO DO BANCO
    echo "💾 Criando backup do banco de dados..."
    BACKUP_DIR="backups"
    mkdir -p "$BACKUP_DIR"
    
    # Nome do backup com timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$BACKUP_DIR/diria_backup_${TIMESTAMP}.db"
    
    # Copiar banco de dados
    cp "instance/diria.db" "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        echo "✅ Backup criado: $BACKUP_FILE"
        
        # SISTEMA INTELIGENTE DE LIMPEZA DE BACKUPS
        echo "🧹 Gerenciando backups antigos..."
        
        # Configurações de retenção
        MAX_BACKUPS=5          # Máximo de backups por tipo
        MAX_DAILY_BACKUPS=7    # Máximo de backups diários
        MAX_SIZE_MB=100        # Tamanho máximo total em MB
        
        # Função para calcular tamanho total dos backups
        calculate_backup_size() {
            local total_size=0
            for backup in "$BACKUP_DIR"/diria_backup_*.db; do
                if [ -f "$backup" ]; then
                    local size=$(stat -c%s "$backup" 2>/dev/null || stat -f%z "$backup" 2>/dev/null || echo 0)
                    total_size=$((total_size + size))
                fi
            done
            echo $((total_size / 1024 / 1024))  # Converter para MB
        }
        
        # 1. Limpeza por quantidade (manter apenas os últimos N)
        echo "  📊 Limpeza por quantidade (mantendo últimos $MAX_BACKUPS)..."
        backup_count=$(ls -1 "$BACKUP_DIR"/diria_backup_*.db 2>/dev/null | wc -l)
        if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
            to_remove=$((backup_count - MAX_BACKUPS))
            ls -t "$BACKUP_DIR"/diria_backup_*.db 2>/dev/null | tail -n "$to_remove" | xargs -r rm
            echo "    ✅ Removidos $to_remove backup(s) antigo(s)"
        else
            echo "    ℹ️  Quantidade dentro do limite ($backup_count/$MAX_BACKUPS)"
        fi
        
        # 2. Limpeza por data (manter apenas backups dos últimos N dias)
        echo "  📅 Limpeza por data (mantendo últimos $MAX_DAILY_BACKUPS dias)..."
        cutoff_date=$(date -d "$MAX_DAILY_BACKUPS days ago" +"%Y%m%d" 2>/dev/null || date -v-${MAX_DAILY_BACKUPS}d +"%Y%m%d" 2>/dev/null || echo "00000000")
        
        for backup in "$BACKUP_DIR"/diria_backup_*.db; do
            if [ -f "$backup" ]; then
                backup_date=$(echo "$backup" | grep -o '[0-9]\{8\}' | head -1)
                if [ "$backup_date" != "" ] && [ "$backup_date" -lt "$cutoff_date" ]; then
                    rm "$backup"
                    echo "    🗑️  Removido backup antigo: $(basename "$backup")"
                fi
            fi
        done
        
        # 3. Limpeza por tamanho (se exceder limite)
        echo "  💾 Verificando tamanho total dos backups..."
        total_size=$(calculate_backup_size)
        if [ "$total_size" -gt "$MAX_SIZE_MB" ]; then
            echo "    ⚠️  Tamanho total: ${total_size}MB (limite: ${MAX_SIZE_MB}MB)"
            echo "    🗑️  Removendo backups mais antigos até atingir o limite..."
            
            while [ "$total_size" -gt "$MAX_SIZE_MB" ] && [ "$(ls -1 "$BACKUP_DIR"/diria_backup_*.db 2>/dev/null | wc -l)" -gt 1 ]; do
                oldest_backup=$(ls -t "$BACKUP_DIR"/diria_backup_*.db 2>/dev/null | tail -1)
                if [ -f "$oldest_backup" ]; then
                    backup_size=$(stat -c%s "$oldest_backup" 2>/dev/null || stat -f%z "$oldest_backup" 2>/dev/null || echo 0)
                    backup_size_mb=$((backup_size / 1024 / 1024))
                    rm "$oldest_backup"
                    total_size=$((total_size - backup_size_mb))
                    echo "      🗑️  Removido: $(basename "$oldest_backup") (${backup_size_mb}MB)"
                else
                    break
                fi
            done
        else
            echo "    ✅ Tamanho total: ${total_size}MB (dentro do limite de ${MAX_SIZE_MB}MB)"
        fi
        
        # 4. Relatório final
        final_count=$(ls -1 "$BACKUP_DIR"/diria_backup_*.db 2>/dev/null | wc -l)
        final_size=$(calculate_backup_size)
        echo "  📋 Relatório final: $final_count backup(s), ${final_size}MB total"
        echo "✅ Gerenciamento de backups concluído"
    else
        echo "❌ ERRO: Falha ao criar backup do banco de dados!"
        echo "⚠️  ABORTANDO DEPLOY por segurança!"
        exit 1
    fi
    
    # Executar migração consolidada (inclui todas as migrações necessárias)
    echo "🔄 Executando migração consolidada..."
    python migrate_db.py
    
    if [ $? -eq 0 ]; then
        echo "✅ Migração consolidada concluída!"
        
        # Verificar se os modelos já foram migrados
        echo "🔍 Verificando se modelos já foram migrados..."
        python -c "
try:
    from app import app, AIModel
    app.app_context().push()
    models = AIModel.query.all()
    print(f'Encontrados {len(models)} modelos no banco')
    if len(models) > 0:
        print('✅ Modelos encontrados - migração não necessária')
        exit(0)
    else:
        print('⚠️  Nenhum modelo encontrado - migração necessária')
        exit(1)
except Exception as e:
    print(f'❌ Erro ao verificar modelos: {e}')
    exit(1)
"
        
        MODEL_CHECK_RESULT=$?
        echo "🔍 Resultado da verificação: $MODEL_CHECK_RESULT"
        
        if [ $MODEL_CHECK_RESULT -ne 0 ]; then
            # Migrar modelos hardcoded para o banco de dados (apenas se não existirem)
            echo "🤖 Migrando modelos de IA para o banco de dados..."
            echo "🔍 Executando: python migrate_models_to_db.py"
            
            # Executar migração com captura de erro detalhada
            python migrate_models_to_db.py 2>&1
            MIGRATION_RESULT=$?
            echo "🔍 Resultado da migração: $MIGRATION_RESULT"
            
            if [ $MIGRATION_RESULT -eq 0 ]; then
                echo "✅ Modelos migrados com sucesso!"
                
                # Verificar novamente após migração
                echo "🔍 Verificando modelos após migração..."
                python -c "
try:
    from app import app, AIModel
    app.app_context().push()
    models = AIModel.query.all()
    print(f'✅ {len(models)} modelos encontrados após migração')
    enabled_models = [m for m in models if m.is_enabled]
    print(f'✅ {len(enabled_models)} modelos habilitados')
except Exception as e:
    print(f'❌ Erro ao verificar modelos após migração: {e}')
    import traceback
    traceback.print_exc()
"
            else
                echo "❌ ERRO: Falha na migração de modelos!"
                echo "🔍 Verificando se a tabela ai_model existe..."
                python -c "
try:
    import sqlite3
    conn = sqlite3.connect('instance/diria.db')
    cursor = conn.cursor()
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='ai_model'\")
    result = cursor.fetchone()
    conn.close()
    if result:
        print('✅ Tabela ai_model existe')
    else:
        print('❌ Tabela ai_model não existe!')
except Exception as e:
    print(f'❌ Erro ao verificar tabela: {e}')
"
                echo "🔄 Restaurando backup..."
                cp "$BACKUP_FILE" "instance/diria.db"
                echo "✅ Backup restaurado. Verifique os logs e tente novamente."
                exit 1
            fi
        else
            echo "ℹ️  Modelos já migrados - pulando migração"
        fi
        
        # Verificar se a tabela model_status ainda existe
        echo "🔍 Verificando se limpeza já foi executada..."
        python -c "
try:
    import sqlite3
    conn = sqlite3.connect('instance/diria.db')
    cursor = conn.cursor()
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='model_status'\")
    result = cursor.fetchone()
    conn.close()
    print(f'Tabela model_status: {\"existe\" if result else \"não existe\"}')
    exit(0 if result else 1)
except Exception as e:
    print(f'Erro ao verificar tabela model_status: {e}')
    exit(1)
" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            # Limpar tabelas desnecessárias (apenas se ainda existirem)
            echo "🧹 Limpando tabelas desnecessárias..."
            python cleanup_db.py
            
            if [ $? -eq 0 ]; then
                echo "✅ Limpeza do banco concluída!"
            else
                echo "⚠️  Aviso: Falha na limpeza do banco (sistema continuará funcionando)"
            fi
        else
            echo "ℹ️  Limpeza já executada - pulando limpeza"
        fi
        
        # Verificar integridade do banco após migração
        echo "🔍 Verificando integridade do banco de dados..."
        python verify_db_integrity.py
        
        if [ $? -eq 0 ]; then
            echo "✅ Integridade do banco verificada com sucesso!"
            
            # Verificar se os modelos estão funcionando corretamente
            echo "🤖 Verificando modelos de IA..."
            python -c "
try:
    from app import app, AIModel
    app.app_context().push()
    models = AIModel.query.all()
    print(f'✅ {len(models)} modelos encontrados no banco')
    enabled_models = [m for m in models if m.is_enabled]
    print(f'✅ {len(enabled_models)} modelos habilitados')
except Exception as e:
    print(f'⚠️  Erro ao verificar modelos: {e}')
"
        else
            echo "❌ ERRO: Problemas de integridade detectados no banco!"
            echo "🔄 Restaurando backup..."
            cp "$BACKUP_FILE" "instance/diria.db"
            echo "✅ Backup restaurado. Verifique os logs e tente novamente."
            exit 1
        fi
    else
        echo "❌ ERRO: Falha na migração do banco de dados!"
        echo "🔄 Restaurando backup..."
        cp "$BACKUP_FILE" "instance/diria.db"
        echo "✅ Backup restaurado. Verifique os logs e tente novamente."
        exit 1
    fi
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

echo "🔑 IMPORTANTE: Configure as chaves de API via painel administrativo!"
echo "   Acesse: https://diria.com.br/admin/api_keys"
echo "   Ou use o arquivo .env como fallback"
echo ""
echo "🤖 NOVO: Sistema de modelos dinâmicos ativo!"
echo "   - Modelos agora são gerenciados via banco de dados"
echo "   - Acesse: https://diria.com.br/admin/config"
echo "   - Habilite/desabilite modelos conforme necessário"
echo ""
echo "📋 Próximos passos:"
echo "   1. Acesse o painel admin: https://diria.com.br/admin"
echo "   2. Vá em 'Gerenciar Chaves de API'"
echo "   3. Configure as chaves de OpenAI, Anthropic e Google"
echo "   4. Vá em 'Configurações' para gerenciar modelos de IA"
echo "   5. Teste a geração de minutas" 