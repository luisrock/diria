#!/usr/bin/env python3
"""
Script para verificar usuários no banco de dados
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_users():
    """Verifica usuários no banco de dados"""
    print("👥 Verificando Usuários no Banco de Dados")
    print("=" * 50)
    
    try:
        from app import app, User, db
        
        with app.app_context():
            users = User.query.all()
            
            if not users:
                print("❌ Nenhum usuário encontrado no banco de dados")
                print("💡 Execute a inicialização do banco:")
                print("   python -c \"from app import init_db; init_db()\"")
                return False
            
            print(f"✅ {len(users)} usuário(s) encontrado(s):")
            print()
            
            for user in users:
                status = "🟢 Ativo" if user.is_active else "🔴 Inativo"
                admin = "👑 Admin" if user.is_admin else "👤 Usuário"
                print(f"📧 {user.email}")
                print(f"   Nome: {user.name}")
                print(f"   Status: {status}")
                print(f"   Tipo: {admin}")
                print(f"   Criado em: {user.created_at.strftime('%d/%m/%Y %H:%M')}")
                print()
            
            # Verificar se há pelo menos um admin
            admins = User.query.filter_by(is_admin=True, is_active=True).all()
            if not admins:
                print("⚠️ Nenhum administrador ativo encontrado!")
            else:
                print(f"✅ {len(admins)} administrador(es) ativo(s)")
            
            return True
            
    except Exception as e:
        print(f"❌ Erro ao verificar usuários: {e}")
        return False

def show_login_info():
    """Mostra informações de login"""
    print("\n🔑 Informações de Login")
    print("=" * 30)
    print("Usuários padrão criados automaticamente:")
    print("• admin@diria.com / admin123 (Administrador)")
    print("• assessor1@diria.com / senha123 (Assessor)")
    print("• assessor2@diria.com / senha456 (Assessor)")
    print()
    print("💡 Para acessar o sistema:")
    print("   ./start.sh                    # macOS/Linux")
    print("   .\\start.ps1                   # Windows")
    print("   http://localhost:5001")

if __name__ == "__main__":
    success = check_users()
    if success:
        show_login_info()
    else:
        print("\n💡 Para resolver:")
        print("1. Verifique se o banco de dados existe")
        print("2. Execute a inicialização: python -c \"from app import init_db; init_db()\"")
        print("3. Execute este script novamente") 