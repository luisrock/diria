#!/usr/bin/env python3
"""
Script de migração do banco de dados DIRIA
Atualiza a estrutura do banco conforme necessário
"""

import os
import sys
from datetime import datetime
from sqlalchemy import text, inspect

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db, init_db

def check_table_exists(table_name):
    """Verifica se uma tabela existe no banco"""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def create_debug_table():
    """Cria a tabela DebugRequest se não existir"""
    if not check_table_exists('debug_request'):
        print("🔄 Criando tabela debug_request...")
        
        # Importar o modelo
        from app import DebugRequest
        
        # Criar a tabela
        DebugRequest.__table__.create(db.engine, checkfirst=True)
        print("✅ Tabela debug_request criada com sucesso!")
        return True
    else:
        print("✅ Tabela debug_request já existe")
        return False

def create_eproc_credentials_table():
    """Cria a tabela EprocCredentials se não existir"""
    if not check_table_exists('eproc_credentials'):
        print("🔄 Criando tabela eproc_credentials...")
        
        # Importar o modelo
        from app import EprocCredentials
        
        # Criar a tabela
        EprocCredentials.__table__.create(db.engine, checkfirst=True)
        print("✅ Tabela eproc_credentials criada com sucesso!")
        return True
    else:
        print("✅ Tabela eproc_credentials já existe")
        return False

def create_ai_model_table():
    """Cria a tabela AIModel se não existir"""
    if not check_table_exists('ai_model'):
        print("🔄 Criando tabela ai_model...")
        
        # Importar o modelo
        from app import AIModel
        
        # Criar a tabela
        AIModel.__table__.create(db.engine, checkfirst=True)
        print("✅ Tabela ai_model criada com sucesso!")
        return True
    else:
        print("✅ Tabela ai_model já existe")
        return False

def migrate_database():
    """Executa todas as migrações necessárias"""
    print("🚀 Iniciando migração do banco de dados...")
    print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("-" * 50)
    
    with app.app_context():
        # Verificar se o banco existe
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Conexão com banco de dados estabelecida")
        except Exception as e:
            print(f"❌ Erro ao conectar com banco: {e}")
            return False
        
        # Lista de migrações
        migrations = [
            ("Tabela DebugRequest", create_debug_table),
            ("Tabela EprocCredentials", create_eproc_credentials_table),
            ("Tabela AIModel", create_ai_model_table),
        ]
        
        # Executar migrações
        changes_made = False
        for migration_name, migration_func in migrations:
            print(f"\n🔄 Executando: {migration_name}")
            try:
                if migration_func():
                    changes_made = True
            except Exception as e:
                print(f"❌ Erro na migração '{migration_name}': {e}")
                return False
        
        if not changes_made:
            print("\n✅ Nenhuma migração necessária - banco está atualizado!")
        else:
            print("\n✅ Migração concluída com sucesso!")
        
        return True

def show_status():
    """Mostra o status atual do banco"""
    print("📊 Status do Banco de Dados")
    print("-" * 30)
    
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"📋 Tabelas encontradas: {len(tables)}")
        for table in sorted(tables):
            print(f"  - {table}")
        
        # Verificar tabelas específicas
        required_tables = [
            'user', 'prompt', 'usage_log', 'app_config', 
            'general_instructions', 
            'api_key', 'eproc_credentials', 'dollar_rate', 
            'ai_model', 'debug_request'
        ]
        
        print(f"\n🔍 Verificação de tabelas obrigatórias:")
        for table in required_tables:
            if table in tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} (faltando)")

def main():
    """Função principal"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'status':
            show_status()
        elif command == 'migrate':
            migrate_database()
        elif command == 'init':
            print("🚀 Inicializando banco de dados...")
            init_db()
        else:
            print("❌ Comando inválido!")
            print("Comandos disponíveis:")
            print("  python migrate_db.py status   - Mostra status do banco")
            print("  python migrate_db.py migrate  - Executa migrações")
            print("  python migrate_db.py init     - Inicializa banco (cria usuários padrão)")
    else:
        # Comportamento padrão: executar migração
        migrate_database() 

if __name__ == '__main__':
    main() 