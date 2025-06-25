#!/usr/bin/env python3
"""
Teste rápido do sistema DIRIA
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Adicionar o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_system():
    """Teste rápido do sistema"""
    print("🚀 Teste Rápido do Sistema DIRIA")
    print("=" * 50)
    
    # Teste 1: Verificar configuração
    print("1. ✅ Verificando configuração...")
    try:
        from ai_manager import ai_manager
        print("   ✅ ai_manager carregado com sucesso")
    except Exception as e:
        print(f"   ❌ Erro ao carregar ai_manager: {e}")
        return False
    
    # Teste 2: Verificar modelos
    print("2. ✅ Verificando modelos...")
    try:
        from models_config import get_all_models
        models = get_all_models()
        print(f"   ✅ {len(models)} modelos configurados")
        print(f"   📋 Modelos: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")
    except Exception as e:
        print(f"   ❌ Erro ao carregar modelos: {e}")
        return False
    
    # Teste 3: Verificar APIs
    print("3. ✅ Verificando APIs...")
    openai_key = os.getenv('OPENAI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    google_key = os.getenv('GOOGLE_API_KEY')
    
    print(f"   OpenAI: {'✅' if openai_key and openai_key != 'sua_chave_openai_aqui' else '❌'}")
    print(f"   Anthropic: {'✅' if anthropic_key and anthropic_key != 'sua_chave_anthropic_aqui' else '❌'}")
    print(f"   Google: {'✅' if google_key and google_key != 'sua_chave_google_aqui' else '❌'}")
    
    # Teste 4: Verificar banco de dados
    print("4. ✅ Verificando banco de dados...")
    db_path = "instance/diria.db"
    if os.path.exists(db_path):
        print("   ✅ Banco de dados existe")
    else:
        print("   ⚠️ Banco de dados não existe (será criado na primeira execução)")
    
    # Teste 5: Verificar streaming
    print("5. ✅ Verificando streaming...")
    try:
        # Verificar se o método de streaming existe
        if hasattr(ai_manager, '_call_anthropic_streaming'):
            print("   ✅ Streaming implementado")
        else:
            print("   ❌ Streaming não implementado")
            return False
    except Exception as e:
        print(f"   ❌ Erro ao verificar streaming: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 Sistema pronto para uso!")
    print("\n💡 Para iniciar:")
    print("   ./start.sh                    # macOS/Linux")
    print("   .\\start.ps1                   # Windows")
    print("\n🌐 Acesso:")
    print("   http://localhost:5001")
    print("   Login: admin@diria.com / admin123")
    
    return True

if __name__ == "__main__":
    success = test_system()
    sys.exit(0 if success else 1) 