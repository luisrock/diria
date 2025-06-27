#!/usr/bin/env python3
"""
Script para verificar a integridade do banco de dados DIRIA
"""

import os
import sqlite3
import sys
from datetime import datetime

def verify_database_integrity():
    """Verifica a integridade do banco de dados"""
    
    db_path = 'instance/diria.db'
    
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado!")
        return False
    
    print("🔍 Verificando integridade do banco de dados...")
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar integridade do SQLite
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()
        
        if integrity_result[0] == "ok":
            print("✅ Integridade do SQLite: OK")
        else:
            print(f"❌ Problema de integridade: {integrity_result[0]}")
            return False
        
        # Verificar tabelas essenciais
        essential_tables = [
            'user', 'usage_log', 'prompt', 'model_instructions', 
            'general_instructions', 'api_key', 'dollar_rate', 
            'model_status', 'app_config'
        ]
        
        print("\n📋 Verificando tabelas essenciais...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = []
        for table in essential_tables:
            if table in existing_tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} - FALTANDO")
                missing_tables.append(table)
        
        if missing_tables:
            print(f"\n⚠️  {len(missing_tables)} tabela(s) essencial(is) não encontrada(s)")
            return False
        
        # Verificar dados críticos
        print("\n📊 Verificando dados críticos...")
        
        # Verificar se há usuários
        cursor.execute("SELECT COUNT(*) FROM user")
        user_count = cursor.fetchone()[0]
        print(f"  👥 Usuários: {user_count}")
        
        # Verificar se há prompts
        cursor.execute("SELECT COUNT(*) FROM prompt")
        prompt_count = cursor.fetchone()[0]
        print(f"  📝 Prompts: {prompt_count}")
        
        # Verificar se há modelos habilitados
        cursor.execute("SELECT COUNT(*) FROM model_status WHERE is_enabled = 1")
        enabled_models = cursor.fetchone()[0]
        print(f"  🤖 Modelos habilitados: {enabled_models}")
        
        # Verificar se há chaves de API
        cursor.execute("SELECT COUNT(*) FROM api_key WHERE is_active = 1")
        active_keys = cursor.fetchone()[0]
        print(f"  🔑 Chaves de API ativas: {active_keys}")
        
        # Verificar logs de uso
        cursor.execute("SELECT COUNT(*) FROM usage_log")
        log_count = cursor.fetchone()[0]
        print(f"  📈 Logs de uso: {log_count}")
        
        conn.close()
        
        print("\n✅ Verificação de integridade concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar integridade: {e}")
        return False

def show_database_info():
    """Mostra informações gerais do banco de dados"""
    
    db_path = 'instance/diria.db'
    
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado!")
        return
    
    # Informações do arquivo
    stat = os.stat(db_path)
    size_mb = stat.st_size / (1024 * 1024)
    modified_time = datetime.fromtimestamp(stat.st_mtime)
    
    print(f"📁 Arquivo: {db_path}")
    print(f"📏 Tamanho: {size_mb:.2f} MB")
    print(f"🕒 Modificado: {modified_time.strftime('%d/%m/%Y %H:%M:%S')}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contar tabelas
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        print(f"📋 Tabelas: {table_count}")
        
        # Listar tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📝 Tabelas: {', '.join(tables)}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro ao obter informações: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "info":
        show_database_info()
    else:
        success = verify_database_integrity()
        if not success:
            sys.exit(1) 