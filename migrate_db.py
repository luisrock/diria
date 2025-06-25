#!/usr/bin/env python3
"""
Script para migrar o banco de dados e adicionar as novas colunas de tokens
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migra o banco de dados para incluir as novas colunas de tokens"""
    
    db_path = 'instance/diria.db'
    
    if not os.path.exists(db_path):
        print("Banco de dados não encontrado. Execute a aplicação primeiro para criar o banco.")
        return
    
    print("Iniciando migração do banco de dados...")
    
    try:
        # Conectar ao banco
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verificar se as colunas já existem
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
                print(f"Adicionando coluna: {column_name}")
                cursor.execute(f"ALTER TABLE usage_log ADD COLUMN {column_name} {column_type}")
        
        # Atualizar registros existentes
        cursor.execute("UPDATE usage_log SET success = 1 WHERE success IS NULL")
        cursor.execute("UPDATE usage_log SET request_tokens = tokens_used WHERE request_tokens IS NULL AND tokens_used > 0")
        
        # Commit das mudanças
        conn.commit()
        print("Migração concluída com sucesso!")
        
        # Mostrar estatísticas
        cursor.execute("SELECT COUNT(*) FROM usage_log")
        total_logs = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(tokens_used) FROM usage_log WHERE tokens_used > 0")
        total_tokens = cursor.fetchone()[0] or 0
        
        print(f"\nEstatísticas:")
        print(f"- Total de logs: {total_logs}")
        print(f"- Total de tokens utilizados: {total_tokens}")
        
    except Exception as e:
        print(f"Erro durante a migração: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database() 