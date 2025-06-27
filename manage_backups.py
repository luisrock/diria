#!/usr/bin/env python3
"""
Script para gerenciar backups do banco de dados DIRIA
"""

import os
import shutil
import sys
from datetime import datetime, timedelta
import glob

def list_backups():
    """Lista todos os backups disponíveis"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("❌ Diretório de backups não encontrado!")
        return
    
    backups = glob.glob(os.path.join(backup_dir, "diria_backup_*.db"))
    
    if not backups:
        print("📭 Nenhum backup encontrado!")
        return
    
    print(f"📋 Encontrados {len(backups)} backup(s):")
    print("-" * 80)
    
    total_size = 0
    for backup in sorted(backups, reverse=True):
        stat = os.stat(backup)
        size_mb = stat.st_size / (1024 * 1024)
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        age_days = (datetime.now() - modified_time).days
        
        total_size += size_mb
        
        print(f"📁 {os.path.basename(backup)}")
        print(f"   📏 Tamanho: {size_mb:.2f} MB")
        print(f"   🕒 Criado: {modified_time.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"   📅 Idade: {age_days} dia(s)")
        print()
    
    print(f"📊 Total: {len(backups)} backup(s), {total_size:.2f} MB")

def create_backup():
    """Cria um novo backup manual"""
    db_path = "instance/diria.db"
    backup_dir = "backups"
    
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado!")
        return False
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"diria_backup_{timestamp}.db")
    
    try:
        shutil.copy2(db_path, backup_file)
        size_mb = os.path.getsize(backup_file) / (1024 * 1024)
        print(f"✅ Backup criado: {os.path.basename(backup_file)}")
        print(f"📏 Tamanho: {size_mb:.2f} MB")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return False

def restore_backup(backup_name):
    """Restaura um backup específico"""
    backup_path = os.path.join("backups", backup_name)
    db_path = "instance/diria.db"
    
    if not os.path.exists(backup_path):
        print(f"❌ Backup não encontrado: {backup_name}")
        return False
    
    # Criar backup do banco atual antes de restaurar
    if os.path.exists(db_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_backup = os.path.join("backups", f"pre_restore_{timestamp}.db")
        shutil.copy2(db_path, current_backup)
        print(f"💾 Backup do banco atual criado: {os.path.basename(current_backup)}")
    
    try:
        shutil.copy2(backup_path, db_path)
        print(f"✅ Backup restaurado: {backup_name}")
        print("⚠️  IMPORTANTE: Reinicie a aplicação para aplicar as mudanças!")
        return True
    except Exception as e:
        print(f"❌ Erro ao restaurar backup: {e}")
        return False

def cleanup_backups(max_backups=5, max_days=7, max_size_mb=100):
    """Limpa backups antigos baseado em critérios"""
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        print("❌ Diretório de backups não encontrado!")
        return
    
    backups = glob.glob(os.path.join(backup_dir, "diria_backup_*.db"))
    
    if not backups:
        print("📭 Nenhum backup para limpar!")
        return
    
    print(f"🧹 Iniciando limpeza de backups...")
    print(f"   📊 Máximo de backups: {max_backups}")
    print(f"   📅 Máximo de dias: {max_days}")
    print(f"   💾 Tamanho máximo: {max_size_mb} MB")
    print()
    
    removed_count = 0
    removed_size = 0
    
    # 1. Limpeza por quantidade
    if len(backups) > max_backups:
        backups.sort(key=os.path.getmtime, reverse=True)
        to_remove = backups[max_backups:]
        
        for backup in to_remove:
            size_mb = os.path.getsize(backup) / (1024 * 1024)
            os.remove(backup)
            removed_count += 1
            removed_size += size_mb
            print(f"🗑️  Removido por quantidade: {os.path.basename(backup)} ({size_mb:.2f} MB)")
    
    # 2. Limpeza por data
    cutoff_date = datetime.now() - timedelta(days=max_days)
    backups = glob.glob(os.path.join(backup_dir, "diria_backup_*.db"))
    
    for backup in backups:
        if os.path.getmtime(backup) < cutoff_date.timestamp():
            size_mb = os.path.getsize(backup) / (1024 * 1024)
            os.remove(backup)
            removed_count += 1
            removed_size += size_mb
            print(f"🗑️  Removido por data: {os.path.basename(backup)} ({size_mb:.2f} MB)")
    
    # 3. Limpeza por tamanho
    backups = glob.glob(os.path.join(backup_dir, "diria_backup_*.db"))
    total_size = sum(os.path.getsize(b) / (1024 * 1024) for b in backups)
    
    if total_size > max_size_mb:
        print(f"⚠️  Tamanho total: {total_size:.2f} MB (limite: {max_size_mb} MB)")
        
        # Ordenar por data (mais antigos primeiro)
        backups.sort(key=os.path.getmtime)
        
        for backup in backups:
            if total_size <= max_size_mb:
                break
            
            size_mb = os.path.getsize(backup) / (1024 * 1024)
            os.remove(backup)
            removed_count += 1
            removed_size += size_mb
            total_size -= size_mb
            print(f"🗑️  Removido por tamanho: {os.path.basename(backup)} ({size_mb:.2f} MB)")
    
    # Relatório final
    remaining_backups = glob.glob(os.path.join(backup_dir, "diria_backup_*.db"))
    remaining_size = sum(os.path.getsize(b) / (1024 * 1024) for b in remaining_backups)
    
    print()
    print(f"✅ Limpeza concluída!")
    print(f"   🗑️  Removidos: {removed_count} backup(s)")
    print(f"   💾 Espaço liberado: {removed_size:.2f} MB")
    print(f"   📋 Restantes: {len(remaining_backups)} backup(s)")
    print(f"   💾 Tamanho total: {remaining_size:.2f} MB")

def show_help():
    """Mostra ajuda do script"""
    print("""
🔧 Gerenciador de Backups DIRIA

Uso: python manage_backups.py [comando] [opções]

Comandos disponíveis:

  list                    Lista todos os backups disponíveis
  create                  Cria um novo backup manual
  restore <backup_name>   Restaura um backup específico
  cleanup                 Limpa backups antigos automaticamente
  help                    Mostra esta ajuda

Exemplos:

  python manage_backups.py list
  python manage_backups.py create
  python manage_backups.py restore diria_backup_20250627_143000.db
  python manage_backups.py cleanup

Configurações de limpeza (no script):
  - Máximo de backups: 5
  - Máximo de dias: 7
  - Tamanho máximo: 100 MB
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_backups()
    elif command == "create":
        create_backup()
    elif command == "restore":
        if len(sys.argv) < 3:
            print("❌ Especifique o nome do backup para restaurar!")
            print("Exemplo: python manage_backups.py restore diria_backup_20250627_143000.db")
            sys.exit(1)
        restore_backup(sys.argv[2])
    elif command == "cleanup":
        cleanup_backups()
    elif command == "help":
        show_help()
    else:
        print(f"❌ Comando desconhecido: {command}")
        show_help()
        sys.exit(1) 