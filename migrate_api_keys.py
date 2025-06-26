#!/usr/bin/env python3
"""
Script para migrar chaves de API do .env para o banco de dados
"""

import os
from dotenv import load_dotenv
from app import app, db, APIKey

def migrate_api_keys():
    """Migra as chaves de API do .env para o banco de dados"""
    with app.app_context():
        # Criar tabela se não existir
        db.create_all()
        
        # Carregar variáveis do .env
        load_dotenv()
        
        # Obter chaves do .env
        openai_key = os.getenv('OPENAI_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        google_key = os.getenv('GOOGLE_API_KEY')
        
        print("🔍 Migrando chaves de API do .env para o banco de dados...")
        
        # Migrar OpenAI
        if openai_key:
            existing = APIKey.query.filter_by(provider='openai').first()
            if existing:
                existing.api_key = openai_key
                existing.is_active = True
                print("✅ OpenAI: Chave atualizada")
            else:
                new_key = APIKey(provider='openai', api_key=openai_key)
                db.session.add(new_key)
                print("✅ OpenAI: Chave criada")
        else:
            print("⚠️ OpenAI: Chave não encontrada no .env")
        
        # Migrar Anthropic
        if anthropic_key:
            existing = APIKey.query.filter_by(provider='anthropic').first()
            if existing:
                existing.api_key = anthropic_key
                existing.is_active = True
                print("✅ Anthropic: Chave atualizada")
            else:
                new_key = APIKey(provider='anthropic', api_key=anthropic_key)
                db.session.add(new_key)
                print("✅ Anthropic: Chave criada")
        else:
            print("⚠️ Anthropic: Chave não encontrada no .env")
        
        # Migrar Google
        if google_key:
            existing = APIKey.query.filter_by(provider='google').first()
            if existing:
                existing.api_key = google_key
                existing.is_active = True
                print("✅ Google: Chave atualizada")
            else:
                new_key = APIKey(provider='google', api_key=google_key)
                db.session.add(new_key)
                print("✅ Google: Chave criada")
        else:
            print("⚠️ Google: Chave não encontrada no .env")
        
        # Commit das alterações
        db.session.commit()
        
        print("\n📊 Resumo da migração:")
        api_keys = APIKey.query.all()
        for key in api_keys:
            status = "✅ Ativa" if key.is_active else "❌ Inativa"
            print(f"  {key.provider}: {status}")
        
        print("\n🎯 Próximos passos:")
        print("1. Acesse o painel administrativo")
        print("2. Vá em 'Gerenciar API Keys'")
        print("3. Teste as chaves para verificar se estão funcionando")
        print("4. Reinicie o serviço para aplicar as mudanças")

if __name__ == "__main__":
    migrate_api_keys() 