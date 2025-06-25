#!/usr/bin/env python3
"""
Script para testar e validar chaves de API
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def test_anthropic_key():
    """Testa a chave da Anthropic"""
    print("🔑 Testando Chave da Anthropic")
    print("=" * 40)
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        print("❌ Chave da Anthropic não configurada!")
        print("💡 Configure ANTHROPIC_API_KEY no arquivo .env")
        return False
    
    if api_key == "sua_chave_anthropic_aqui":
        print("❌ Chave da Anthropic não foi alterada!")
        print("💡 Substitua 'sua_chave_anthropic_aqui' pela sua chave real")
        return False
    
    print(f"📝 Chave encontrada: {api_key[:20]}...{api_key[-10:]}")
    
    # Verificar formato da chave
    if not api_key.startswith("sk-ant-api"):
        print("⚠️ Formato da chave parece incorreto")
        print("💡 Chaves da Anthropic devem começar com 'sk-ant-api'")
        return False
    
    try:
        import anthropic
        
        # Testar conexão
        client = anthropic.Anthropic(api_key=api_key)
        
        # Tentar uma requisição simples
        print("🔄 Testando conexão...")
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Diga apenas 'OK'"}]
        )
        
        print("✅ Chave válida! Conexão bem-sucedida")
        print(f"📄 Resposta: {response.content[0].text}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erro na validação: {error_msg}")
        
        if "401" in error_msg or "authentication_error" in error_msg:
            print("\n🔧 Possíveis soluções:")
            print("1. Verifique se a chave está correta")
            print("2. A chave pode ter expirado")
            print("3. Verifique se tem créditos na conta")
            print("4. Gere uma nova chave em: https://console.anthropic.com/")
        elif "rate_limit" in error_msg:
            print("\n⏱️ Rate limit atingido. Tente novamente em alguns minutos.")
        else:
            print("\n🔍 Verifique a documentação da Anthropic para mais detalhes.")
        
        return False

def test_openai_key():
    """Testa a chave da OpenAI"""
    print("\n🔑 Testando Chave da OpenAI")
    print("=" * 40)
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ Chave da OpenAI não configurada!")
        return False
    
    if api_key == "sua_chave_openai_aqui":
        print("❌ Chave da OpenAI não foi alterada!")
        return False
    
    print(f"📝 Chave encontrada: {api_key[:20]}...{api_key[-10:]}")
    
    # Verificar formato da chave
    if not api_key.startswith("sk-"):
        print("⚠️ Formato da chave parece incorreto")
        return False
    
    try:
        import openai
        
        # Testar conexão
        client = openai.OpenAI(api_key=api_key)
        
        print("🔄 Testando conexão...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=10,
            messages=[{"role": "user", "content": "Diga apenas 'OK'"}]
        )
        
        print("✅ Chave válida! Conexão bem-sucedida")
        print(f"📄 Resposta: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erro na validação: {error_msg}")
        return False

def test_google_key():
    """Testa a chave do Google"""
    print("\n🔑 Testando Chave do Google")
    print("=" * 40)
    
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ Chave do Google não configurada!")
        return False
    
    if api_key == "sua_chave_google_aqui":
        print("❌ Chave do Google não foi alterada!")
        return False
    
    print(f"📝 Chave encontrada: {api_key[:20]}...{api_key[-10:]}")
    
    try:
        import google.generativeai as genai
        
        # Testar conexão
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        print("🔄 Testando conexão...")
        response = model.generate_content("Diga apenas 'OK'")
        
        print("✅ Chave válida! Conexão bem-sucedida")
        print(f"📄 Resposta: {response.text}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erro na validação: {error_msg}")
        return False

def show_help():
    """Mostra ajuda para configurar as chaves"""
    print("\n📚 Como Configurar Chaves de API")
    print("=" * 50)
    
    print("\n🔑 Anthropic (Claude):")
    print("1. Acesse: https://console.anthropic.com/")
    print("2. Faça login ou crie uma conta")
    print("3. Vá em 'API Keys'")
    print("4. Clique em 'Create Key'")
    print("5. Copie a chave (começa com 'sk-ant-api')")
    print("6. Cole no arquivo .env")
    
    print("\n🔑 OpenAI (GPT):")
    print("1. Acesse: https://platform.openai.com/api-keys")
    print("2. Faça login ou crie uma conta")
    print("3. Clique em 'Create new secret key'")
    print("4. Copie a chave (começa com 'sk-')")
    print("5. Cole no arquivo .env")
    
    print("\n🔑 Google (Gemini):")
    print("1. Acesse: https://makersuite.google.com/app/apikey")
    print("2. Faça login com sua conta Google")
    print("3. Clique em 'Create API Key'")
    print("4. Copie a chave")
    print("5. Cole no arquivo .env")
    
    print("\n💡 Exemplo de arquivo .env:")
    print("ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    print("OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    print("GOOGLE_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

def main():
    """Função principal"""
    print("🔑 Validador de Chaves de API - DIRIA")
    print("=" * 50)
    
    # Testar cada chave
    anthropic_ok = test_anthropic_key()
    openai_ok = test_openai_key()
    google_ok = test_google_key()
    
    print("\n" + "=" * 50)
    print("📊 Resumo dos Testes:")
    print(f"Anthropic: {'✅' if anthropic_ok else '❌'}")
    print(f"OpenAI: {'✅' if openai_ok else '❌'}")
    print(f"Google: {'✅' if google_ok else '❌'}")
    
    if not any([anthropic_ok, openai_ok, google_ok]):
        print("\n⚠️ Nenhuma chave válida encontrada!")
        print("💡 O sistema funcionará em modo simulado")
        show_help()
    else:
        print("\n🎉 Pelo menos uma chave está funcionando!")
        print("💡 O sistema pode usar APIs reais")
    
    print("\n💡 Para usar o sistema:")
    print("./start.sh                    # macOS/Linux")
    print(".\\start.ps1                   # Windows")

if __name__ == "__main__":
    main() 