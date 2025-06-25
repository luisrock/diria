"""
Configuração dos modelos de IA por fabricante
Facilita a adição de novos modelos conforme são lançados
"""

# Configuração dos modelos por fabricante
MODELS_CONFIG = {
    "openai": {
        "name": "OpenAI",
        "prefix": "o",
        "encoder": "gpt",  # Usa encoder específico do modelo
        "models": {
            "o3-2025-04-16": {
                "display_name": "O3",
                "description": "Our most powerful reasoning model, but slow",
                "max_tokens": 100000,
                "context_window": 200000,
                "price_input": 2.0,  # $2 / MTok
                "price_output": 8.0,  # $8 / MTok
                "available": True
            },
            "o4-mini-2025-04-16": {
                "display_name": "O4 Mini",
                "description": "Faster, more affordable reasoning model",
                "max_tokens": 100000,
                "context_window": 200000,
                "price_input": 1.10,  # $1.10 / MTok
                "price_output": 4.40,  # $4.40 / MTok
                "available": True
            }
        }
    },
    
    "anthropic": {
        "name": "Anthropic",
        "prefix": "claude-",
        "encoder": "cl100k_base",  # Claude usa cl100k_base
        "models": {
            "claude-sonnet-4-20250514": {
                "display_name": "Claude Sonnet 4",
                "description": "High-performance model",
                "max_tokens": 64000,
                "context_window": 200000,
                "price_input": 3.0,  # $3 / MTok
                "price_output": 15.0,  # $15 / MTok
                "available": True
            },
            "claude-3-7-sonnet-20250219": {
                "display_name": "Claude Sonnet 3.7",
                "description": "High-performance model with early extended thinking",
                "max_tokens": 64000,
                "context_window": 200000,
                "price_input": 3.0,  # $3 / MTok
                "price_output": 15.0,  # $15 / MTok
                "available": True
            }
        }
    },
    
    "google": {
        "name": "Google",
        "prefix": "gemini-",
        "encoder": "cl100k_base",  # Aproximação para Gemini
        "models": {
            "gemini-2.5-pro": {
                "display_name": "Gemini 2.5 Pro",
                "description": "State-of-the-art thinking model",
                "max_tokens": 65000,
                "context_window": 1000000,
                "price_input": 2.50,  # $2.50 / MTok
                "price_output": 15.0,  # $15 / MTok
                "available": True
            },
            "gemini-2.5-flash": {
                "display_name": "Gemini 2.5 Flash",
                "description": "Our best model in terms of price-performance, offering well-rounded capabilities",
                "max_tokens": 65000,
                "context_window": 1000000,
                "price_input": 0.30,  # $0.30 / MTok
                "price_output": 2.50,  # $2.50 / MTok
                "available": True
            }
        }
    }
}

def get_all_models() -> list:
    """Retorna lista de todos os modelos disponíveis"""
    models = []
    for provider, config in MODELS_CONFIG.items():
        for model_id, model_info in config["models"].items():
            if model_info["available"]:
                models.append(model_id)
    return models

def get_models_by_provider(provider: str) -> list:
    """Retorna lista de modelos de um fabricante específico"""
    if provider not in MODELS_CONFIG:
        return []
    
    models = []
    for model_id, model_info in MODELS_CONFIG[provider]["models"].items():
        if model_info["available"]:
            models.append(model_id)
    return models

def get_model_info(model_id: str) -> dict:
    """Retorna informações de um modelo específico"""
    for provider, config in MODELS_CONFIG.items():
        if model_id in config["models"]:
            return {
                "provider": provider,
                "provider_name": config["name"],
                "model_id": model_id,
                **config["models"][model_id]
            }
    return None

def get_provider_for_model(model_id: str) -> str:
    """Retorna o fabricante de um modelo"""
    for provider, config in MODELS_CONFIG.items():
        if model_id in config["models"]:
            return provider
    return None

def calculate_cost(request_tokens: int, response_tokens: int, model_id: str) -> dict:
    """
    Calcula o custo estimado de uma requisição
    
    Args:
        request_tokens: Tokens de entrada
        response_tokens: Tokens de saída
        model_id: ID do modelo usado
    
    Returns:
        Dict com custos detalhados
    """
    model_info = get_model_info(model_id)
    if not model_info:
        return {"total_cost": 0, "input_cost": 0, "output_cost": 0, "currency": "USD"}
    
    # Converter tokens para MTok (1 MTok = 1,000,000 tokens)
    input_mtok = request_tokens / 1_000_000
    output_mtok = response_tokens / 1_000_000
    
    # Calcular custos
    input_cost = input_mtok * model_info.get("price_input", 0)
    output_cost = output_mtok * model_info.get("price_output", 0)
    total_cost = input_cost + output_cost
    
    return {
        "total_cost": total_cost,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "currency": "USD",
        "model_name": model_info["display_name"],
        "price_input": model_info.get("price_input", 0),
        "price_output": model_info.get("price_output", 0)
    }

def add_new_model(provider: str, model_id: str, display_name: str, description: str, max_tokens: int = 32768, context_window: int = 32768, price_input: float = 0, price_output: float = 0):
    """
    Adiciona um novo modelo à configuração
    
    Args:
        provider: Fabricante (openai, anthropic, google)
        model_id: ID do modelo
        display_name: Nome para exibição
        description: Descrição do modelo
        max_tokens: Limite de tokens de saída
        context_window: Janela de contexto
        price_input: Preço por MTok de entrada
        price_output: Preço por MTok de saída
    """
    if provider not in MODELS_CONFIG:
        raise ValueError(f"Fabricante '{provider}' não suportado")
    
    MODELS_CONFIG[provider]["models"][model_id] = {
        "display_name": display_name,
        "description": description,
        "max_tokens": max_tokens,
        "context_window": context_window,
        "price_input": price_input,
        "price_output": price_output,
        "available": True
    }
    
    print(f"✅ Modelo '{model_id}' adicionado ao fabricante '{provider}'")

def disable_model(model_id: str):
    """Desabilita um modelo"""
    for provider, config in MODELS_CONFIG.items():
        if model_id in config["models"]:
            config["models"][model_id]["available"] = False
            print(f"✅ Modelo '{model_id}' desabilitado")
            return
    
    print(f"❌ Modelo '{model_id}' não encontrado")

def enable_model(model_id: str):
    """Habilita um modelo"""
    for provider, config in MODELS_CONFIG.items():
        if model_id in config["models"]:
            config["models"][model_id]["available"] = True
            print(f"✅ Modelo '{model_id}' habilitado")
            return
    
    print(f"❌ Modelo '{model_id}' não encontrado")

def list_models_by_provider():
    """Lista todos os modelos organizados por fabricante"""
    for provider, config in MODELS_CONFIG.items():
        print(f"\n🔹 {config['name']}:")
        for model_id, model_info in config["models"].items():
            status = "✅" if model_info["available"] else "❌"
            print(f"  {status} {model_id} - {model_info['display_name']}")
            print(f"     {model_info['description']}")
            print(f"     Context Window: {model_info['context_window']:,} tokens")
            print(f"     Max Output: {model_info['max_tokens']:,} tokens")
            print(f"     Price: ${model_info['price_input']}/MTok input, ${model_info['price_output']}/MTok output")

# Exemplo de uso para adicionar novos modelos:
if __name__ == "__main__":
    print("🤖 Configuração de Modelos de IA")
    print("=" * 40)
    
    # Listar modelos atuais
    list_models_by_provider()
    
    print("\n📝 Para adicionar um novo modelo:")
    print("add_new_model('openai', 'o5', 'O5', 'Novo modelo da OpenAI', 100000, 200000, 2.5, 10.0)")
    print("add_new_model('anthropic', 'claude-4', 'Claude 4', 'Novo modelo da Anthropic', 64000, 200000, 3.5, 18.0)")
    print("add_new_model('google', 'gemini-3.0', 'Gemini 3.0', 'Novo modelo do Google', 65000, 1000000, 1.0, 8.0)") 