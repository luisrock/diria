#!/usr/bin/env python3
"""
Script consolidado para migrar o banco de dados DIRIA
Inclui todas as migrações necessárias para o sistema
"""

import sqlite3
import os
import sys
from datetime import datetime, timezone

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Migra o banco de dados para incluir todas as novas funcionalidades"""
    
    db_path = 'instance/diria.db'
    
    if not os.path.exists(db_path):
        print("Banco de dados não encontrado. Execute a aplicação primeiro para criar o banco.")
        return
    
    print("🔄 Iniciando migração consolidada do banco de dados DIRIA...")
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ========================================
        # 1. MIGRAÇÃO DE TOKENS (existente)
        # ========================================
        print("\n📊 1. Migrando colunas de tokens...")
        
        cursor.execute("PRAGMA table_info(usage_log)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Adicionar novas colunas se não existirem
        new_columns = [
            ('request_tokens', 'INTEGER DEFAULT 0'),
            ('response_tokens', 'INTEGER DEFAULT 0'),
            ('model_used', 'VARCHAR(50)'),
            ('success', 'BOOLEAN DEFAULT 1'),
            ('error_message', 'TEXT')
        ]
        
        for column_name, column_type in new_columns:
            if column_name not in columns:
                print(f"  ➕ Adicionando coluna: {column_name}")
                cursor.execute(f"ALTER TABLE usage_log ADD COLUMN {column_name} {column_type}")
            else:
                print(f"  ✅ Coluna {column_name} já existe")
        
        # Atualizar registros existentes
        cursor.execute("UPDATE usage_log SET success = 1 WHERE success IS NULL")
        cursor.execute("UPDATE usage_log SET request_tokens = tokens_used WHERE request_tokens IS NULL AND tokens_used > 0")
        
        # ========================================
        # 2. MIGRAÇÃO DE INSTRUÇÕES
        # ========================================
        print("\n📝 2. Migrando instruções dos modelos...")
        
        # Verificar se a tabela model_instructions existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_instructions'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela model_instructions...")
            cursor.execute("""
                CREATE TABLE model_instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id VARCHAR(100) UNIQUE NOT NULL,
                    instructions TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            print("  ✅ Tabela model_instructions já existe")
        
        # Verificar se a tabela general_instructions existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='general_instructions'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela general_instructions...")
            cursor.execute("""
                CREATE TABLE general_instructions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instructions TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Inserir instruções padrão
            default_instructions = """Você é um juiz experiente especializado em direito civil, com mais de 20 anos de experiência no Poder Judiciário. 

Suas decisões devem ser baseadas apenas nos fatos apresentados e na legislação aplicável. Use linguagem formal e técnica apropriada para documentos judiciais.

Não mencione nomes de pessoas físicas ou jurídicas específicas. Não faça suposições sobre fatos não apresentados. Base suas decisões apenas nos dados fornecidos e na legislação aplicável."""
            
            cursor.execute("INSERT INTO general_instructions (instructions) VALUES (?)", (default_instructions,))
            print("  ✅ Instruções gerais padrão inseridas")
        else:
            print("  ✅ Tabela general_instructions já existe")
        
        # ========================================
        # 3. MIGRAÇÃO DE CHAVES DE API
        # ========================================
        print("\n🔑 3. Migrando chaves de API...")
        
        # Verificar se a tabela api_key existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_key'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela api_key...")
            cursor.execute("""
                CREATE TABLE api_key (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider VARCHAR(50) UNIQUE NOT NULL,
                    api_key TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            print("  ✅ Tabela api_key já existe")
        
        # ========================================
        # 4. MIGRAÇÃO DE TAXA DE CÂMBIO
        # ========================================
        print("\n💱 4. Migrando taxa de câmbio...")
        
        # Verificar se a tabela dollar_rate existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dollar_rate'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela dollar_rate...")
            cursor.execute("""
                CREATE TABLE dollar_rate (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rate FLOAT NOT NULL,
                    date DATE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            print("  ✅ Tabela dollar_rate já existe")
        
        # ========================================
        # 5. MIGRAÇÃO DE STATUS DOS MODELOS
        # ========================================
        print("\n🤖 5. Migrando status dos modelos...")
        
        # Verificar se a tabela model_status existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_status'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela model_status...")
            cursor.execute("""
                CREATE TABLE model_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id VARCHAR(100) UNIQUE NOT NULL,
                    is_enabled BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Inserir status padrão para todos os modelos
            try:
                from models_config import get_all_models
                all_models = get_all_models()
                
                for model_id in all_models:
                    cursor.execute("INSERT INTO model_status (model_id, is_enabled) VALUES (?, ?)", (model_id, True))
                    print(f"  ✅ Status criado para modelo: {model_id}")
                
                print(f"  📊 Total de {len(all_models)} modelos configurados")
            except ImportError:
                print("  ⚠️  Não foi possível importar models_config - status dos modelos não criado")
        else:
            print("  ✅ Tabela model_status já existe")
            
            # Verificar se há modelos sem status
            try:
                from models_config import get_all_models
                all_models = get_all_models()
                
                for model_id in all_models:
                    cursor.execute("SELECT id FROM model_status WHERE model_id = ?", (model_id,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO model_status (model_id, is_enabled) VALUES (?, ?)", (model_id, True))
                        print(f"  ➕ Status criado para modelo: {model_id}")
            except ImportError:
                print("  ⚠️  Não foi possível verificar modelos faltantes")
        
        # ========================================
        # 6. MIGRAÇÃO DE CONFIGURAÇÕES DA APLICAÇÃO
        # ========================================
        print("\n⚙️ 6. Migrando configurações da aplicação...")
        
        # Verificar se a tabela app_config existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_config'")
        if not cursor.fetchone():
            print("  ➕ Criando tabela app_config...")
            cursor.execute("""
                CREATE TABLE app_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Inserir configurações padrão
            default_configs = [
                ('default_ai_model', 'gemini-2.5-pro', 'Modelo de IA padrão da aplicação')
            ]
            
            for key, value, description in default_configs:
                cursor.execute("INSERT INTO app_config (key, value, description) VALUES (?, ?, ?)", (key, value, description))
                print(f"  ✅ Configuração criada: {key}")
        else:
            print("  ✅ Tabela app_config já existe")
        
        # Commit de todas as mudanças
        conn.commit()
        print("\n✅ Migração consolidada concluída com sucesso!")
        
        # ========================================
        # 7. ESTATÍSTICAS FINAIS
        # ========================================
        print("\n📊 Estatísticas finais:")
        
        # Contar logs
        cursor.execute("SELECT COUNT(*) FROM usage_log")
        total_logs = cursor.fetchone()[0]
        print(f"  📋 Total de logs: {total_logs}")
        
        # Contar tokens
        cursor.execute("SELECT SUM(tokens_used) FROM usage_log WHERE tokens_used > 0")
        total_tokens = cursor.fetchone()[0] or 0
        print(f"  🧮 Total de tokens utilizados: {total_tokens}")
        
        # Contar modelos configurados
        cursor.execute("SELECT COUNT(*) FROM model_status")
        total_models = cursor.fetchone()[0]
        print(f"  🤖 Modelos configurados: {total_models}")
        
        # Contar chaves de API
        cursor.execute("SELECT COUNT(*) FROM api_key")
        total_keys = cursor.fetchone()[0]
        print(f"  🔑 Chaves de API configuradas: {total_keys}")
        
        # Contar prompts
        cursor.execute("SELECT COUNT(*) FROM prompt")
        total_prompts = cursor.fetchone()[0]
        print(f"  📝 Prompts configurados: {total_prompts}")
        
        # Contar usuários
        cursor.execute("SELECT COUNT(*) FROM user")
        total_users = cursor.fetchone()[0]
        print(f"  👥 Usuários cadastrados: {total_users}")
        
    except Exception as e:
        print(f"❌ Erro durante a migração: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def show_migration_status():
    """Mostra o status atual das migrações"""
    db_path = 'instance/diria.db'
    
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📋 Status das migrações:")
        print("-" * 50)
        
        # Verificar tabelas
        tables = [
            'usage_log', 'user', 'prompt', 'model_instructions', 
            'general_instructions', 'api_key', 'dollar_rate', 
            'model_status', 'app_config'
        ]
        
        for table in tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone():
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"✅ {table}: {count} registros")
            else:
                print(f"❌ {table}: não existe")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao verificar status: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        show_migration_status()
    else:
        migrate_database() 