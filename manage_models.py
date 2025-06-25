#!/usr/bin/env python3
"""
Script interativo para gerenciar modelos de IA
Facilita a adição, remoção e configuração de modelos
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models_config import (
    MODELS_CONFIG, 
    get_all_models, 
    get_models_by_provider, 
    get_model_info,
    add_new_model, 
    disable_model, 
    enable_model,
    list_models_by_provider
)

def print_header():
    """Imprime cabeçalho do script"""
    print("🤖 Gerenciador de Modelos de IA - DIRIA")
    print("=" * 50)

def print_menu():
    """Imprime menu principal"""
    print("\n📋 Menu Principal:")
    print("1. 📋 Listar todos os modelos")
    print("2. ➕ Adicionar novo modelo")
    print("3. ❌ Desabilitar modelo")
    print("4. ✅ Habilitar modelo")
    print("5. 🔍 Ver detalhes de um modelo")
    print("6. 📊 Estatísticas")
    print("7. 🚪 Sair")
    print("-" * 30)

def list_all_models():
    """Lista todos os modelos"""
    print("\n📋 Modelos Configurados:")
    list_models_by_provider()
    
    # Estatísticas
    total_models = len(get_all_models())
    print(f"\n📊 Total de modelos ativos: {total_models}")

def add_model_interactive():
    """Adiciona um novo modelo de forma interativa"""
    print("\n➕ Adicionar Novo Modelo")
    print("-" * 30)
    
    # Escolher fabricante
    print("\n🔹 Fabricantes disponíveis:")
    for i, provider in enumerate(MODELS_CONFIG.keys(), 1):
        print(f"{i}. {MODELS_CONFIG[provider]['name']}")
    
    try:
        choice = int(input("\nEscolha o fabricante (1-3): ")) - 1
        providers = list(MODELS_CONFIG.keys())
        if choice < 0 or choice >= len(providers):
            print("❌ Opção inválida!")
            return
        provider = providers[choice]
    except ValueError:
        print("❌ Entrada inválida!")
        return
    
    # Coletar informações do modelo
    print(f"\n📝 Configurando modelo para {MODELS_CONFIG[provider]['name']}")
    
    model_id = input("ID do modelo (ex: gpt-5, claude-4): ").strip()
    if not model_id:
        print("❌ ID do modelo é obrigatório!")
        return
    
    display_name = input("Nome para exibição: ").strip()
    if not display_name:
        display_name = model_id
    
    description = input("Descrição: ").strip()
    if not description:
        description = "Novo modelo"
    
    try:
        max_tokens = int(input("Limite de tokens (padrão: 32768): ") or "32768")
    except ValueError:
        max_tokens = 32768
    
    # Adicionar modelo
    try:
        add_new_model(provider, model_id, display_name, description, max_tokens)
        print(f"\n✅ Modelo '{model_id}' adicionado com sucesso!")
        print("💡 Reinicie a aplicação para usar o novo modelo.")
    except Exception as e:
        print(f"❌ Erro ao adicionar modelo: {e}")

def disable_model_interactive():
    """Desabilita um modelo de forma interativa"""
    print("\n❌ Desabilitar Modelo")
    print("-" * 30)
    
    models = get_all_models()
    if not models:
        print("❌ Nenhum modelo ativo encontrado!")
        return
    
    print("\n🔹 Modelos ativos:")
    for i, model in enumerate(models, 1):
        info = get_model_info(model)
        print(f"{i}. {model} - {info['display_name']}")
    
    try:
        choice = int(input("\nEscolha o modelo para desabilitar: ")) - 1
        if choice < 0 or choice >= len(models):
            print("❌ Opção inválida!")
            return
        model = models[choice]
        disable_model(model)
    except ValueError:
        print("❌ Entrada inválida!")

def enable_model_interactive():
    """Habilita um modelo de forma interativa"""
    print("\n✅ Habilitar Modelo")
    print("-" * 30)
    
    # Encontrar modelos desabilitados
    disabled_models = []
    for provider, config in MODELS_CONFIG.items():
        for model_id, model_info in config["models"].items():
            if not model_info["available"]:
                disabled_models.append(model_id)
    
    if not disabled_models:
        print("❌ Nenhum modelo desabilitado encontrado!")
        return
    
    print("\n🔹 Modelos desabilitados:")
    for i, model in enumerate(disabled_models, 1):
        info = get_model_info(model)
        print(f"{i}. {model} - {info['display_name']}")
    
    try:
        choice = int(input("\nEscolha o modelo para habilitar: ")) - 1
        if choice < 0 or choice >= len(disabled_models):
            print("❌ Opção inválida!")
            return
        model = disabled_models[choice]
        enable_model(model)
    except ValueError:
        print("❌ Entrada inválida!")

def show_model_details():
    """Mostra detalhes de um modelo específico"""
    print("\n🔍 Detalhes do Modelo")
    print("-" * 30)
    
    models = get_all_models()
    if not models:
        print("❌ Nenhum modelo ativo encontrado!")
        return
    
    print("\n🔹 Modelos disponíveis:")
    for i, model in enumerate(models, 1):
        info = get_model_info(model)
        print(f"{i}. {model} - {info['display_name']}")
    
    try:
        choice = int(input("\nEscolha o modelo para ver detalhes: ")) - 1
        if choice < 0 or choice >= len(models):
            print("❌ Opção inválida!")
            return
        model = models[choice]
        
        info = get_model_info(model)
        print(f"\n📋 Detalhes do modelo '{model}':")
        print(f"   Fabricante: {info['provider_name']}")
        print(f"   Nome: {info['display_name']}")
        print(f"   Descrição: {info['description']}")
        print(f"   Max tokens: {info['max_tokens']:,}")
        print(f"   Status: {'✅ Ativo' if info['available'] else '❌ Inativo'}")
        
    except ValueError:
        print("❌ Entrada inválida!")

def show_statistics():
    """Mostra estatísticas dos modelos"""
    print("\n📊 Estatísticas dos Modelos")
    print("-" * 30)
    
    total_models = 0
    active_models = 0
    
    for provider, config in MODELS_CONFIG.items():
        provider_models = len(config["models"])
        provider_active = len([m for m in config["models"].values() if m["available"]])
        
        print(f"\n🔹 {config['name']}:")
        print(f"   Total: {provider_models}")
        print(f"   Ativos: {provider_active}")
        print(f"   Inativos: {provider_models - provider_active}")
        
        total_models += provider_models
        active_models += provider_active
    
    print(f"\n📈 Resumo Geral:")
    print(f"   Total de modelos: {total_models}")
    print(f"   Modelos ativos: {active_models}")
    print(f"   Modelos inativos: {total_models - active_models}")

def main():
    """Função principal"""
    print_header()
    
    while True:
        print_menu()
        
        try:
            choice = input("\nEscolha uma opção (1-7): ").strip()
            
            if choice == "1":
                list_all_models()
            elif choice == "2":
                add_model_interactive()
            elif choice == "3":
                disable_model_interactive()
            elif choice == "4":
                enable_model_interactive()
            elif choice == "5":
                show_model_details()
            elif choice == "6":
                show_statistics()
            elif choice == "7":
                print("\n👋 Até logo!")
                break
            else:
                print("❌ Opção inválida! Escolha de 1 a 7.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Até logo!")
            break
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main() 