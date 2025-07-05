"""
Configuração dos modelos de IA por fabricante
Facilita a adição de novos modelos conforme são lançados
"""

# Configuração dos modelos de IA por fabricante
# NOTA: Esta configuração foi migrada para o banco de dados
# Os modelos agora são gerenciados dinamicamente através da tabela AIModel

def get_all_models() -> list:
    """Retorna lista de todos os modelos disponíveis (apenas do banco)"""
    try:
        from app import AIModel
        # Carregar do banco
        db_models = AIModel.query.filter_by(is_enabled=True).all()
        return [model.model_id for model in db_models]
    except Exception as e:
        print(f"⚠️  Erro ao carregar modelos do banco: {e}")
        return []  # Retornar lista vazia se não conseguir acessar banco

def get_models_by_provider(provider: str) -> list:
    """Retorna lista de modelos de um fabricante específico (apenas do banco)"""
    try:
        from app import app, AIModel
        with app.app_context():
            models = AIModel.query.filter_by(provider=provider, is_enabled=True).all()
            return [model.model_id for model in models]
    except Exception as e:
        print(f"⚠️  Erro ao carregar modelos do provedor {provider}: {e}")
        return []

def get_model_info(model_id: str) -> dict:
    """Retorna informações de um modelo específico (apenas do banco)"""
    try:
        from app import app, AIModel
        with app.app_context():
            # Buscar no banco (sem filtrar por is_enabled)
            model = AIModel.query.filter_by(model_id=model_id).first()
            if model:
                return {
                    "provider": model.provider,
                    "provider_name": model.provider.title(),
                    "model_id": model.model_id,
                    "display_name": model.display_name,
                    "description": model.description,
                    "max_tokens": model.max_tokens,
                    "context_window": model.context_window,
                    "price_input": model.price_input,
                    "price_output": model.price_output,
                    "available": model.is_enabled
                }
    except Exception as e:
        print(f"⚠️  Erro ao buscar modelo no banco: {e}")
    
    return None  # Retornar None se não encontrar no banco

def get_provider_for_model(model_id: str) -> str:
    """Retorna o fabricante de um modelo (apenas do banco)"""
    try:
        from app import app, AIModel
        with app.app_context():
            model = AIModel.query.filter_by(model_id=model_id).first()
            return model.provider if model else None
    except Exception as e:
        print(f"⚠️  Erro ao buscar provedor do modelo: {e}")
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
    Adiciona um novo modelo ao banco de dados
    
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
    try:
        from app import app, AIModel, db
        with app.app_context():
            # Verificar se o modelo já existe
            existing = AIModel.query.filter_by(model_id=model_id).first()
            if existing:
                print(f"⚠️  Modelo '{model_id}' já existe no banco")
                return
            
            # Criar novo modelo
            model = AIModel(
                name=model_id,  # Usar model_id como name
                provider=provider,
                model_id=model_id,
                display_name=display_name,
                description=description,
                max_tokens=max_tokens,
                context_window=context_window,
                price_input=price_input,
                price_output=price_output,
                is_enabled=True
            )
            db.session.add(model)
            db.session.commit()
            print(f"✅ Modelo '{model_id}' adicionado ao banco")
    except Exception as e:
        print(f"❌ Erro ao adicionar modelo: {e}")

def disable_model(model_id: str):
    """Desabilita um modelo no banco"""
    try:
        from app import app, AIModel, db
        with app.app_context():
            model = AIModel.query.filter_by(model_id=model_id).first()
            if model:
                model.is_enabled = False
                db.session.commit()
                print(f"✅ Modelo '{model_id}' desabilitado")
            else:
                print(f"❌ Modelo '{model_id}' não encontrado")
    except Exception as e:
        print(f"❌ Erro ao desabilitar modelo: {e}")

def enable_model(model_id: str):
    """Habilita um modelo no banco"""
    try:
        from app import app, AIModel, db
        with app.app_context():
            model = AIModel.query.filter_by(model_id=model_id).first()
            if model:
                model.is_enabled = True
                db.session.commit()
                print(f"✅ Modelo '{model_id}' habilitado")
            else:
                print(f"❌ Modelo '{model_id}' não encontrado")
    except Exception as e:
        print(f"❌ Erro ao habilitar modelo: {e}")

def list_models_by_provider():
    """Lista todos os modelos organizados por fabricante (apenas do banco)"""
    try:
        from app import app, AIModel
        with app.app_context():
            models = AIModel.query.all()
            if not models:
                print("📭 Nenhum modelo encontrado no banco")
                return
            
            # Agrupar por provedor
            by_provider = {}
            for model in models:
                if model.provider not in by_provider:
                    by_provider[model.provider] = []
                by_provider[model.provider].append(model)
            
            for provider, provider_models in by_provider.items():
                print(f"\n🔹 {provider.title()}:")
                for model in provider_models:
                    status = "✅" if model.is_enabled else "❌"
                    print(f"  {status} {model.model_id} - {model.display_name}")
                    print(f"     {model.description}")
                    print(f"     Context Window: {model.context_window:,} tokens")
                    print(f"     Max Output: {model.max_tokens:,} tokens")
                    print(f"     Price: ${model.price_input}/MTok input, ${model.price_output}/MTok output")
    except Exception as e:
        print(f"❌ Erro ao listar modelos: {e}")

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