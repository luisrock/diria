#!/usr/bin/env python3
"""
Script para migrar modelos hardcoded para o banco de dados
Executado automaticamente durante o deploy
"""

import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, AIModel
from datetime import datetime, timezone

def migrate_models_to_db():
    """Migra modelos hardcoded para o banco de dados"""
    print("🤖 Iniciando migração de modelos hardcoded para o banco de dados...")
    print("🔍 Verificando ambiente...")
    
    try:
        from app import app, db, AIModel
        print("✅ Imports do app realizados com sucesso")
    except Exception as e:
        print(f"❌ Erro nos imports do app: {e}")
        return False
    
    # Modelos hardcoded atuais
    hardcoded_models = [
        # OpenAI
        {
            'name': 'o3-2025-04-16',
            'provider': 'openai',
            'model_id': 'o3-2025-04-16',
            'display_name': 'O3',
            'description': 'Our most powerful reasoning model, but slow',
            'max_tokens': 100000,
            'context_window': 200000,
            'price_input': 2.0,
            'price_output': 8.0
        },
        {
            'name': 'o4-mini-2025-04-16',
            'provider': 'openai',
            'model_id': 'o4-mini-2025-04-16',
            'display_name': 'O4 Mini',
            'description': 'Faster, more affordable reasoning model',
            'max_tokens': 100000,
            'context_window': 200000,
            'price_input': 1.10,
            'price_output': 4.40
        },
        # Anthropic
        {
            'name': 'claude-sonnet-4-20250514',
            'provider': 'anthropic',
            'model_id': 'claude-sonnet-4-20250514',
            'display_name': 'Claude Sonnet 4',
            'description': 'High-performance model',
            'max_tokens': 64000,
            'context_window': 200000,
            'price_input': 3.0,
            'price_output': 15.0
        },
        {
            'name': 'claude-3-7-sonnet-20250219',
            'provider': 'anthropic',
            'model_id': 'claude-3-7-sonnet-20250219',
            'display_name': 'Claude Sonnet 3.7',
            'description': 'High-performance model with early extended thinking',
            'max_tokens': 64000,
            'context_window': 200000,
            'price_input': 3.0,
            'price_output': 15.0
        },
        # Google
        {
            'name': 'gemini-2.5-pro',
            'provider': 'google',
            'model_id': 'gemini-2.5-pro',
            'display_name': 'Gemini 2.5 Pro',
            'description': 'State-of-the-art thinking model',
            'max_tokens': 65000,
            'context_window': 1000000,
            'price_input': 2.50,
            'price_output': 15.0
        },
        {
            'name': 'gemini-2.5-flash',
            'provider': 'google',
            'model_id': 'gemini-2.5-flash',
            'display_name': 'Gemini 2.5 Flash',
            'description': 'Our best model in terms of price-performance, offering well-rounded capabilities',
            'max_tokens': 65000,
            'context_window': 1000000,
            'price_input': 0.30,
            'price_output': 2.50
        }
    ]
    
    with app.app_context():
        try:
            print("🔍 Verificando se a tabela AIModel existe...")
            # Verificar se a tabela existe
            try:
                # Tentar fazer uma query simples para verificar se a tabela existe
                result = AIModel.query.first()
                print(f"✅ Tabela AIModel existe (primeiro registro: {result})")
            except Exception as e:
                print(f"❌ Tabela AIModel não existe: {e}")
                print("💡 Execute primeiro: python -c 'from app import app, db; app.app_context().push(); db.create_all()'")
                return False
            
            # Migrar modelos
            added_count = 0
            updated_count = 0
            
            for model_data in hardcoded_models:
                existing = AIModel.query.filter_by(model_id=model_data['model_id']).first()
                
                if not existing:
                    # Criar novo modelo
                    model = AIModel(**model_data)
                    db.session.add(model)
                    print(f"✅ Adicionado: {model_data['display_name']} ({model_data['provider']})")
                    added_count += 1
                else:
                    # Atualizar modelo existente
                    for key, value in model_data.items():
                        if key != 'name':  # Não atualizar o name (ID interno)
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now(timezone.utc)
                    print(f"🔄 Atualizado: {model_data['display_name']} ({model_data['provider']})")
                    updated_count += 1
            
            # Commit das mudanças
            db.session.commit()
            
            print(f"🎉 Migração concluída!")
            print(f"   ✅ Adicionados: {added_count} modelos")
            print(f"   🔄 Atualizados: {updated_count} modelos")
            
            # Verificar total de modelos
            total_models = AIModel.query.count()
            enabled_models = AIModel.query.filter_by(is_enabled=True).count()
            print(f"   📊 Total no banco: {total_models} modelos ({enabled_models} ativos)")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro durante migração: {e}")
            db.session.rollback()
            return False

def list_models():
    """Lista todos os modelos no banco de dados"""
    with app.app_context():
        try:
            models = AIModel.query.all()
            if not models:
                print("📭 Nenhum modelo encontrado no banco de dados")
                return
            
            print("📋 Modelos no banco de dados:")
            print("-" * 80)
            for model in models:
                status = "✅ Ativo" if model.is_enabled else "❌ Inativo"
                print(f"{model.display_name:20} | {model.provider:10} | {model.model_id:25} | {status}")
            print("-" * 80)
            
        except Exception as e:
            print(f"❌ Erro ao listar modelos: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migração de modelos de IA')
    parser.add_argument('--list', action='store_true', help='Listar modelos no banco')
    parser.add_argument('--migrate', action='store_true', help='Migrar modelos hardcoded')
    
    args = parser.parse_args()
    
    if args.list:
        list_models()
    elif args.migrate:
        success = migrate_models_to_db()
        if success:
            print("✅ Migração executada com sucesso!")
        else:
            print("❌ Falha na migração!")
            sys.exit(1)
    else:
        # Executar migração por padrão
        success = migrate_models_to_db()
        if success:
            print("✅ Migração executada com sucesso!")
        else:
            print("❌ Falha na migração!")
            sys.exit(1) 