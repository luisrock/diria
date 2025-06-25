#!/usr/bin/env python3
"""
Script para debugar variáveis de ambiente
"""

import os
from dotenv import load_dotenv

def debug_env():
    """Debuga as variáveis de ambiente"""
    print("🔍 Debug das Variáveis de Ambiente")
    print("=" * 50)
    
    # Carregar .env
    print("1. Carregando arquivo .env...")
    load_dotenv()
    
    # Verificar chaves
    print("\n2. Verificando chaves de API:")
    
    openai_key = os.getenv('OPENAI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    google_key = os.getenv('GOOGLE_API_KEY')
    
    print(f"OPENAI_API_KEY: {'✅ Configurada' if openai_key else '❌ Não configurada'}")
    if openai_key:
        print(f"   Valor: {openai_key[:20]}...{openai_key[-10:]}")
        print(f"   Tamanho: {len(openai_key)} caracteres")
        print(f"   Começa com 'sk-': {openai_key.startswith('sk-')}")
    
    print(f"\nANTHROPIC_API_KEY: {'✅ Configurada' if anthropic_key else '❌ Não configurada'}")
    if anthropic_key:
        print(f"   Valor: {anthropic_key[:20]}...{anthropic_key[-10:]}")
        print(f"   Tamanho: {len(anthropic_key)} caracteres")
        print(f"   Começa com 'sk-ant-api': {anthropic_key.startswith('sk-ant-api')}")
    
    print(f"\nGOOGLE_API_KEY: {'✅ Configurada' if google_key else '❌ Não configurada'}")
    if google_key:
        print(f"   Valor: {google_key[:20]}...{google_key[-10:]}")
        print(f"   Tamanho: {len(google_key)} caracteres")
        print(f"   Começa com 'AIza': {google_key.startswith('AIza')}")
    
    # Verificar se são valores padrão
    print("\n3. Verificando se são valores padrão:")
    if openai_key == "sua_chave_openai_aqui":
        print("❌ OPENAI_API_KEY ainda tem valor padrão")
    else:
        print("✅ OPENAI_API_KEY foi alterada")
    
    if anthropic_key == "sua_chave_anthropic_aqui":
        print("❌ ANTHROPIC_API_KEY ainda tem valor padrão")
    else:
        print("✅ ANTHROPIC_API_KEY foi alterada")
    
    if google_key == "sua_chave_google_aqui":
        print("❌ GOOGLE_API_KEY ainda tem valor padrão")
    else:
        print("✅ GOOGLE_API_KEY foi alterada")
    
    # Testar leitura direta do arquivo
    print("\n4. Lendo arquivo .env diretamente:")
    try:
        with open('.env', 'r') as f:
            content = f.read()
            lines = content.split('\n')
            
        for line in lines:
            if line.startswith('OPENAI_API_KEY='):
                print(f"OPENAI_API_KEY no arquivo: {line[:30]}...")
            elif line.startswith('ANTHROPIC_API_KEY='):
                print(f"ANTHROPIC_API_KEY no arquivo: {line[:30]}...")
            elif line.startswith('GOOGLE_API_KEY='):
                print(f"GOOGLE_API_KEY no arquivo: {line[:30]}...")
    except Exception as e:
        print(f"❌ Erro ao ler arquivo .env: {e}")
    
    # Testar ai_manager
    print("\n5. Testando ai_manager:")
    try:
        from ai_manager import ai_manager
        
        print("✅ ai_manager importado com sucesso")
        
        # Verificar se os clientes foram configurados
        if ai_manager.openai_client:
            print("✅ Cliente OpenAI configurado")
        else:
            print("❌ Cliente OpenAI não configurado")
            
        if ai_manager.anthropic_client:
            print("✅ Cliente Anthropic configurado")
        else:
            print("❌ Cliente Anthropic não configurado")
            
        if ai_manager.google_genai:
            print("✅ Cliente Google configurado")
        else:
            print("❌ Cliente Google não configurado")
            
    except Exception as e:
        print(f"❌ Erro ao importar ai_manager: {e}")

if __name__ == "__main__":
    debug_env() 