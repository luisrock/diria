#!/usr/bin/env python3
"""
Script para limpeza do banco de dados
Remove tabelas desnecessárias após a migração para AIModel
"""

import sqlite3
from pathlib import Path

def cleanup_database():
    """Remove tabelas desnecessárias do banco de dados"""
    db_path = Path("instance/diria.db")
    
    if not db_path.exists():
        print("❌ Banco de dados não encontrado")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🧹 Iniciando limpeza do banco de dados...")
        
        # Verificar se a tabela model_status existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_status'")
        if cursor.fetchone():
            print("🗑️  Removendo tabela model_status...")
            cursor.execute("DROP TABLE model_status")
            print("✅ Tabela model_status removida")
        else:
            print("ℹ️  Tabela model_status não encontrada (já foi removida)")
        
        # Verificar se há dados órfãos
        cursor.execute("SELECT COUNT(*) FROM ai_model")
        model_count = cursor.fetchone()[0]
        print(f"📊 Modelos na tabela ai_model: {model_count}")
        
        # Commit das mudanças
        conn.commit()
        conn.close()
        
        print("✅ Limpeza concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante a limpeza: {e}")
        return False

if __name__ == "__main__":
    cleanup_database() 