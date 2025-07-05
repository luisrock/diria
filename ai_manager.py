import os
import tiktoken
import openai
import anthropic
from typing import Dict, List, Tuple, Optional
import json
import logging
from datetime import datetime
from models_config import get_all_models, get_model_info, get_provider_for_model
import pprint
from sqlalchemy import text
from google import genai
from google.genai import types

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenUsageManager:
    """Gerenciador de uso de tokens e custos para múltiplas APIs"""
    
    def __init__(self):
        self.token_counter = TokenCounter()
    
    def calculate_cost_from_api_response(self, usage_data: Dict, model: str) -> Dict:
        """
        Calcula custo baseado na resposta da API (mais preciso)
        
        Args:
            usage_data: Dados de uso da API (input_tokens, output_tokens, etc.)
            model: ID do modelo usado
            
        Returns:
            Dict com custos detalhados
        """
        try:
            from models_config import calculate_cost
            
            input_tokens = usage_data.get('input_tokens', 0)
            output_tokens = usage_data.get('output_tokens', 0)
            
            # Calcular custo usando a função existente
            cost_info = calculate_cost(input_tokens, output_tokens, model)
            
            # Adicionar informações de cache se disponíveis
            cache_creation = usage_data.get('cache_creation_tokens', 0)
            cache_read = usage_data.get('cache_read_tokens', 0)
            
            cost_info.update({
                'cache_creation_input_tokens': cache_creation,
                'cache_read_input_tokens': cache_read,
                'api_provided': True
            })
            
            return cost_info
            
        except Exception as e:
            logger.error(f"Erro ao calcular custo da API: {e}")
            return self._fallback_cost_calculation(usage_data, model)
    
    def calculate_cost_from_estimation(self, prompt: str, response: str, model: str) -> Dict:
        """
        Calcula custo baseado em estimativa com tiktoken (fallback)
        
        Args:
            prompt: Texto do prompt
            response: Texto da resposta
            model: ID do modelo usado
            
        Returns:
            Dict com custos detalhados
        """
        try:
            from models_config import calculate_cost
            
            input_tokens = self.token_counter.count_tokens(prompt, model)
            output_tokens = self.token_counter.count_tokens(response, model)
            
            cost_info = calculate_cost(input_tokens, output_tokens, model)
            cost_info.update({
                'api_provided': False,
                'estimated': True
            })
            
            return cost_info
            
        except Exception as e:
            logger.error(f"Erro ao calcular custo estimado: {e}")
            return {
                'total_cost': 0,
                'input_cost': 0,
                'output_cost': 0,
                'currency': 'USD',
                'api_provided': False,
                'estimated': False,
                'error': str(e)
            }
    
    def _fallback_cost_calculation(self, usage_data: Dict, model: str) -> Dict:
        """Fallback para cálculo de custo quando API falha"""
        return {
            'total_cost': 0,
            'input_cost': 0,
            'output_cost': 0,
            'currency': 'USD',
            'api_provided': False,
            'estimated': False,
            'error': 'Falha no cálculo de custo'
        }
    
    def format_cost_for_display(self, cost_info: Dict) -> Dict:
        """
        Formata informações de custo para exibição na interface
        
        Args:
            cost_info: Informações de custo calculadas
            
        Returns:
            Dict formatado para exibição
        """
        return {
            'total_cost_usd': f"${cost_info.get('total_cost', 0):.6f}",
            'input_cost_usd': f"${cost_info.get('input_cost', 0):.6f}",
            'output_cost_usd': f"${cost_info.get('output_cost', 0):.6f}",
            'input_tokens': cost_info.get('input_tokens', 0),
            'output_tokens': cost_info.get('output_tokens', 0),
            'total_tokens': cost_info.get('input_tokens', 0) + cost_info.get('output_tokens', 0),
            'model_name': cost_info.get('model_name', 'Desconhecido'),
            'api_provided': cost_info.get('api_provided', False),
            'estimated': cost_info.get('estimated', False),
            'cache_info': {
                'creation_tokens': cost_info.get('cache_creation_tokens', 0),
                'read_tokens': cost_info.get('cache_read_tokens', 0)
            }
        }

class TokenCounter:
    """Classe para contar tokens usando tiktoken"""
    
    def __init__(self):
        self.encoders = {}
    
    def get_encoder(self, model: str) -> tiktoken.Encoding:
        """Obtém o encoder apropriado para o modelo"""
        if model not in self.encoders:
            try:
                # Obter informações do modelo
                model_info = get_model_info(model)
                if model_info:
                    provider = model_info["provider"]
                    # Obter encoder do banco de dados
                    try:
                        from app import app, AIModel
                        with app.app_context():
                            model = AIModel.query.filter_by(provider=provider).first()
                            encoder_type = model.encoder if model and hasattr(model, 'encoder') else "gpt"
                    except Exception as e:
                        print(f"⚠️  Erro ao buscar encoder do provedor {provider}: {e}")
                        encoder_type = "gpt"  # Fallback
                    
                    if encoder_type == "gpt":
                        # Usar encoder específico do modelo GPT/O
                        try:
                            self.encoders[model] = tiktoken.encoding_for_model(model)
                        except:
                            # Fallback para cl100k_base se modelo não for reconhecido
                            self.encoders[model] = tiktoken.get_encoding("cl100k_base")
                    else:
                        # Usar encoder padrão (cl100k_base para Claude e Gemini)
                        self.encoders[model] = tiktoken.get_encoding("cl100k_base")
                else:
                    # Fallback para cl100k_base
                    self.encoders[model] = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"Erro ao obter encoder para {model}: {e}")
                # Fallback para cl100k_base
                self.encoders[model] = tiktoken.get_encoding("cl100k_base")
        
        return self.encoders[model]
    
    def count_tokens(self, text: str, model: str) -> int:
        """Conta tokens em um texto para um modelo específico"""
        try:
            if text is None:
                text = ""
            encoder = self.get_encoder(model)
            return len(encoder.encode(text))
        except Exception as e:
            logger.error(f"Erro ao contar tokens: {e}")
            # Fallback: estimativa aproximada (1 token ≈ 4 caracteres)
            return len(text) // 4

class AIManager:
    """Gerenciador de APIs de IA"""
    
    def __init__(self):
        self.token_counter = TokenCounter()
        self.token_usage_manager = TokenUsageManager()
        
        # Configurar APIs
        self.openai_client = None
        self.anthropic_client = None
        self.google_genai = None
        
        self._setup_clients()
    
    def _setup_clients(self):
        """Configura os clientes das APIs"""
        # OpenAI
        openai_api_key = self._get_api_key_from_db('openai')
        if openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                logger.info("Cliente OpenAI configurado")
            except Exception as e:
                logger.error(f"Erro ao configurar OpenAI: {e}")
        
        # Anthropic
        anthropic_api_key = self._get_api_key_from_db('anthropic')
        logger.info(f"[ANTHROPIC-SETUP] API Key encontrada: {anthropic_api_key is not None}")
        if anthropic_api_key:
            try:
                logger.info(f"[ANTHROPIC-SETUP] Configurando cliente com chave: {anthropic_api_key[:10]}...")
                self.anthropic_client = anthropic.Anthropic(
                    api_key=anthropic_api_key,
                    timeout=600.0  # 10 minutos de timeout
                )
                logger.info("[ANTHROPIC-SETUP] Cliente Anthropic configurado com sucesso")
            except Exception as e:
                logger.error(f"[ANTHROPIC-SETUP] Erro ao configurar Anthropic: {type(e).__name__}: {str(e)}")
                logger.error(f"[ANTHROPIC-SETUP] Traceback:", exc_info=True)
        else:
            logger.warning("[ANTHROPIC-SETUP] API Key não encontrada no banco de dados")
        
        # Google
        google_api_key = self._get_api_key_from_db('google')
        if google_api_key:
            try:
                # Nova API do Google Gemini não usa configure()
                # A API key é passada diretamente no cliente
                self.google_genai = genai
                self.google_api_key = google_api_key
                logger.info("Cliente Google configurado")
            except Exception as e:
                logger.error(f"Erro ao configurar Google: {e}")
    
    def _get_api_key_from_db(self, provider):
        """Obtém a chave de API do banco de dados"""
        try:
            # Importar aqui para evitar dependência circular
            from flask import current_app
            
            # Verificar se estamos no contexto da aplicação Flask
            if current_app and current_app.app_context():
                # Importar dentro do contexto para evitar circular import
                from app import db, APIKey
                
                api_key = APIKey.query.filter_by(provider=provider, is_active=True).first()
                return api_key.api_key if api_key else None
            else:
                # Se não estiver no contexto, tentar ler do .env como fallback
                import os
                from dotenv import load_dotenv
                load_dotenv()
                
                if provider == 'openai':
                    return os.getenv('OPENAI_API_KEY')
                elif provider == 'anthropic':
                    return os.getenv('ANTHROPIC_API_KEY')
                elif provider == 'google':
                    return os.getenv('GOOGLE_API_KEY')
                return None
        except Exception as e:
            # Log apenas se for um erro real, não apenas falta de contexto
            if "not registered" not in str(e) and "app_context" not in str(e):
                logger.warning(f"Erro ao obter chave da API {provider} do banco: {e}")
            
            # Fallback para .env
            try:
                import os
                from dotenv import load_dotenv
                load_dotenv()
                
                if provider == 'openai':
                    return os.getenv('OPENAI_API_KEY')
                elif provider == 'anthropic':
                    return os.getenv('ANTHROPIC_API_KEY')
                elif provider == 'google':
                    return os.getenv('GOOGLE_API_KEY')
            except:
                pass
            return None
    
    def count_request_tokens(self, prompt: str, model: str) -> int:
        """Conta tokens da requisição (prompt)"""
        return self.token_counter.count_tokens(prompt, model)
    
    def count_response_tokens(self, response: str, model: str) -> int:
        """Conta tokens da resposta"""
        return self.token_counter.count_tokens(response, model)
    
    def generate_response(self, prompt: str, model: str, max_tokens: int = 2000) -> Tuple[str, Dict]:
        """
        Gera resposta usando a API apropriada
        
        Returns:
            Tuple[str, Dict]: (resposta, metadados com contagem de tokens e custos)
        """
        tokens_info = {
            'request_tokens': 0,
            'response_tokens': 0,
            'total_tokens': 0,
            'model_used': model,
            'success': False,
            'error': None,
            'cost_info': None,
            'display_info': None
        }
        
        try:
            # Obter informações do modelo
            model_info = get_model_info(model)
            if not model_info:
                tokens_info['error'] = f"Modelo '{model}' não encontrado na configuração"
                return f"Erro: Modelo '{model}' não configurado", tokens_info
            
            provider = model_info["provider"]
            
            # Ajustar max_tokens baseado no provedor
            if max_tokens == 2000:  # Valor padrão
                if provider == "google":
                    # Gemini precisa de mais tokens devido aos "pensamentos" internos
                    max_tokens = 500  # Mínimo para Gemini funcionar
                else:
                    max_tokens = model_info.get("max_tokens", 2000)
            
            # Aplicar instruções específicas do modelo (sem dependência do app.py)
            system_message = self._get_model_instructions(model)
            if system_message:
                # Armazenar system message para uso nos métodos de chamada
                self._current_system_message = system_message
            
            # Contar tokens após aplicar instruções (fallback)
            tokens_info['request_tokens'] = self.count_request_tokens(prompt, model)
            
            if provider == "openai" and self.openai_client:
                response, api_info = self._call_openai(prompt, model, max_tokens)
                # Usar informações da API se disponíveis, senão usar estimativa
                if api_info.get('success') and api_info.get('usage_data'):
                    tokens_info.update(api_info)
                    tokens_info['request_tokens'] = api_info['usage_data']['input_tokens']
                    tokens_info['response_tokens'] = api_info['usage_data']['output_tokens']
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                else:
                    # Fallback para estimativa
                    tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                    tokens_info['success'] = api_info.get('success', False)
                    tokens_info['error'] = api_info.get('error')
                    tokens_info['cost_info'] = api_info.get('cost_info')
                    tokens_info['display_info'] = api_info.get('display_info')
                return response, tokens_info
                
            elif provider == "anthropic" and self.anthropic_client:
                if len(prompt) > 1000:
                    response, api_info = self._call_anthropic_streaming(prompt, model, max_tokens, system_message)
                else:
                    response, api_info = self._call_anthropic(prompt, model, max_tokens)
                
                # Usar informações da API se disponíveis, senão usar estimativa
                if api_info.get('success') and api_info.get('usage_data'):
                    tokens_info.update(api_info)
                    tokens_info['request_tokens'] = api_info['usage_data']['input_tokens']
                    tokens_info['response_tokens'] = api_info['usage_data']['output_tokens']
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                else:
                    # Fallback para estimativa
                    tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                    tokens_info['success'] = api_info.get('success', False)
                    tokens_info['error'] = api_info.get('error')
                    tokens_info['cost_info'] = api_info.get('cost_info')
                    tokens_info['display_info'] = api_info.get('display_info')
                return response, tokens_info
                
            elif provider == "google" and self.google_genai:
                response, api_info = self._call_google(prompt, model, max_tokens)
                # Usar informações da API se disponíveis, senão usar estimativa
                if api_info.get('success') and api_info.get('usage_data'):
                    tokens_info.update(api_info)
                    tokens_info['request_tokens'] = api_info['usage_data']['input_tokens']
                    tokens_info['response_tokens'] = api_info['usage_data']['output_tokens']
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                else:
                    # Fallback para estimativa
                    tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                    tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                    tokens_info['success'] = api_info.get('success', False)
                    tokens_info['error'] = api_info.get('error')
                    tokens_info['cost_info'] = api_info.get('cost_info')
                    tokens_info['display_info'] = api_info.get('display_info')
                return response, tokens_info
                
            else:
                # Fallback: simulação
                api_name = model_info.get("provider_name", provider)
                tokens_info['error'] = f"API {api_name} não configurada para modelo {model}"
                fallback_response = self._simulate_response(prompt)
                cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, fallback_response, model)
                tokens_info['cost_info'] = cost_info
                tokens_info['display_info'] = self.token_usage_manager.format_cost_for_display(cost_info)
                return fallback_response, tokens_info
                
        except Exception as e:
            tokens_info['error'] = str(e)
            logger.error(f"Erro ao gerar resposta: {e}")
            # Manter os tokens de request mesmo em caso de erro
            tokens_info['total_tokens'] = tokens_info['request_tokens']
            return f"Erro na geração: {str(e)}", tokens_info
    
    def _call_openai(self, prompt: str, model: str, max_tokens: int) -> Tuple[str, Dict]:
        """Chama API da OpenAI e retorna resposta com informações de tokens"""
        import json
        from datetime import datetime
        # Verificar se há system message disponível
        system_message = None
        if hasattr(self, '_current_system_message'):
            system_message = self._current_system_message
            delattr(self, '_current_system_message')
        
        # Preparar mensagens
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # OpenAI O3/O4 só aceita temperature = 1
        temperature = 1
        
        # Log do payload para debug
        logger.debug("[OpenAI] Payload enviado:")
        logger.debug(pprint.pformat({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }))
        
        # Preparar parâmetros da requisição
        request_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        # Usar max_completion_tokens para modelos O3/O4, max_tokens para outros
        if model.startswith('o3-') or model.startswith('o4-'):
            request_params["max_completion_tokens"] = max_tokens
            logger.debug(f"[OpenAI] Usando max_completion_tokens para modelo {model}")
        else:
            request_params["max_tokens"] = max_tokens
            logger.debug(f"[OpenAI] Usando max_tokens para modelo {model}")
        
        try:
            response = self.openai_client.chat.completions.create(**request_params)
            
            # Extrair texto da resposta
            response_text = response.choices[0].message.content
            
            # Capturar dados de uso da API
            usage_data = {
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            # Salvar resposta completa para debug
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "provider": "openai",
                "model": model,
                "system_message": system_message,
                "prompt": prompt,
                "messages": messages,
                "request_params": request_params,
                "response_text": response_text,
                "usage_data": usage_data,
                "raw_response": str(response)
            }
            with open("debug_response_openai.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Calcular custo usando dados da API
            cost_info = self.token_usage_manager.calculate_cost_from_api_response(usage_data, model)
            
            # Formatar para exibição
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return response_text, {
                'success': True,
                'model_used': model,
                'provider': 'openai',
                'usage_data': usage_data,
                'cost_info': cost_info,
                'display_info': display_info
            }
            
        except Exception as e:
            logger.error(f"Erro na API OpenAI: {e}")
            # Fallback com estimativa
            fallback_response = f"Erro na API OpenAI: {str(e)}"
            cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, fallback_response, model)
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return fallback_response, {
                'success': False,
                'model_used': model,
                'provider': 'openai',
                'error': str(e),
                'cost_info': cost_info,
                'display_info': display_info
            }
    
    def _call_anthropic(self, prompt: str, model: str, max_tokens: int) -> Tuple[str, Dict]:
        """Chama API da Anthropic e retorna resposta com informações de tokens"""
        import json
        from datetime import datetime
        
        # Log detalhado para debug
        logger.debug(f"[ANTHROPIC] Iniciando chamada para modelo: {model}")
        logger.debug(f"[ANTHROPIC] Cliente configurado: {self.anthropic_client is not None}")
        
        system_message = None
        if hasattr(self, '_current_system_message'):
            system_message = self._current_system_message
            delattr(self, '_current_system_message')
        
        request_params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        if system_message:
            request_params["system"] = system_message
        
        # Log do payload (apenas em debug)
        logger.debug(f"[ANTHROPIC] Payload: {json.dumps(request_params, indent=2, ensure_ascii=False)}")
        
        try:
            logger.debug(f"[ANTHROPIC] Fazendo chamada para API...")
            response = self.anthropic_client.messages.create(**request_params)
            logger.debug(f"[ANTHROPIC] Resposta recebida com sucesso")
            response_text = response.content[0].text if response.content else ""
            usage_data = None
            if hasattr(response, 'usage') and response.usage:
                usage_data = {
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                }
            
            # Salvar resposta completa para debug
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "provider": "anthropic",
                "model": model,
                "system_message": system_message,
                "prompt": prompt,
                "request_params": request_params,
                "response_text": response_text,
                "usage_data": usage_data,
                "raw_response": str(response)
            }
            with open("debug_response_anthropic.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Calcular custo usando dados da API se disponíveis
            cost_info = self.token_usage_manager.calculate_cost_from_api_response(usage_data, model) if usage_data else self.token_usage_manager.calculate_cost_from_estimation(prompt, response_text, model)
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return response_text, {
                'success': True,
                'model_used': model,
                'provider': 'anthropic',
                'usage_data': usage_data,
                'cost_info': cost_info,
                'display_info': display_info
            }
        except Exception as e:
            logger.error(f"[ANTHROPIC] Erro detalhado: {type(e).__name__}: {str(e)}")
            logger.error(f"[ANTHROPIC] Traceback completo:", exc_info=True)
            
            # Log adicional para debug
            import traceback
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "model": model,
                "max_tokens": max_tokens,
                "has_system_message": system_message is not None,
                "prompt_length": len(prompt) if prompt else 0
            }
            logger.error(f"[ANTHROPIC] Detalhes do erro: {json.dumps(error_details, indent=2)}")
            
            fallback_response = f"Erro na API Anthropic: {str(e)}"
            cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, fallback_response, model)
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            return fallback_response, {
                'success': False,
                'model_used': model,
                'provider': 'anthropic',
                'error': str(e),
                'cost_info': cost_info,
                'display_info': display_info
            }
    
    def _call_anthropic_streaming(self, prompt: str, model: str, max_tokens: int, system_message: str = None) -> Tuple[str, Dict]:
        """Chama API da Anthropic em modo streaming e retorna resposta com informações de tokens"""
        # Anthropic aceita temperature de 0.0 a 1.0 - usar 0.3 para área jurídica
        temperature = 0.3
        
        # Log detalhado para debug
        logger.debug(f"[ANTHROPIC-STREAMING] Iniciando chamada para modelo: {model}")
        logger.debug(f"[ANTHROPIC-STREAMING] Cliente configurado: {self.anthropic_client is not None}")
        
        # Log do payload para debug
        logger.debug("[ANTHROPIC-STREAMING] Payload enviado:")
        logger.debug(pprint.pformat({
            "model": model,
            "system": system_message,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }))
        
        # Preparar parâmetros da requisição
        request_params = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": True
        }
        
        # Adicionar system message apenas se existir
        if system_message:
            request_params["system"] = system_message
        
        try:
            logger.debug(f"[ANTHROPIC-STREAMING] Fazendo chamada para API...")
            response = self.anthropic_client.messages.create(**request_params)
            logger.debug(f"[ANTHROPIC-STREAMING] Resposta streaming iniciada")
            full_response = ""
            usage_data = None
            
            logger.debug(f"[ANTHROPIC-STREAMING] Processando chunks da resposta...")
            chunk_count = 0
            for chunk in response:
                chunk_count += 1
                logger.debug(f"[ANTHROPIC-STREAMING] Chunk {chunk_count}: type={chunk.type}")
                
                if chunk.type == "content_block_delta":
                    full_response += chunk.delta.text
                    logger.debug(f"[ANTHROPIC-STREAMING] Adicionado texto: {len(chunk.delta.text)} chars")
                elif chunk.type == "message_stop":
                    logger.debug(f"[ANTHROPIC-STREAMING] Mensagem finalizada após {chunk_count} chunks")
                    # Capturar dados de uso no evento final
                    if hasattr(chunk, 'usage') and chunk.usage:
                        usage_data = {
                            'input_tokens': chunk.usage.input_tokens,
                            'output_tokens': chunk.usage.output_tokens,
                            'cache_creation_input_tokens': getattr(chunk.usage, 'cache_creation_input_tokens', 0),
                            'cache_read_input_tokens': getattr(chunk.usage, 'cache_read_input_tokens', 0)
                        }
                        logger.debug(f"[ANTHROPIC-STREAMING] Usage data capturado: {usage_data}")
            
            logger.debug(f"[ANTHROPIC-STREAMING] Resposta completa: {len(full_response)} caracteres")
            
            # Calcular custo usando dados da API se disponíveis
            if usage_data:
                cost_info = self.token_usage_manager.calculate_cost_from_api_response(usage_data, model)
            else:
                # Fallback para estimativa
                cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, full_response, model)
            
            # Formatar para exibição
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            logger.debug(f"[ANTHROPIC-STREAMING] Retornando resposta com sucesso")
            logger.debug(f"[ANTHROPIC-STREAMING] Tamanho da resposta: {len(full_response)} caracteres")
            
            return full_response, {
                'success': True,
                'model_used': model,
                'provider': 'anthropic',
                'usage_data': usage_data,
                'cost_info': cost_info,
                'display_info': display_info
            }
            
        except Exception as e:
            logger.error(f"[ANTHROPIC-STREAMING] Erro detalhado: {type(e).__name__}: {str(e)}")
            logger.error(f"[ANTHROPIC-STREAMING] Traceback completo:", exc_info=True)
            
            # Log adicional para debug
            import traceback
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "model": model,
                "max_tokens": max_tokens,
                "has_system_message": system_message is not None,
                "prompt_length": len(prompt) if prompt else 0,
                "streaming": True
            }
            logger.error(f"[ANTHROPIC-STREAMING] Detalhes do erro: {json.dumps(error_details, indent=2)}")
            
            # Fallback com estimativa
            fallback_response = f"Erro na API Anthropic: {str(e)}"
            cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, fallback_response, model)
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return fallback_response, {
                'success': False,
                'model_used': model,
                'provider': 'anthropic',
                'error': str(e),
                'cost_info': cost_info,
                'display_info': display_info
            }
    
    def _call_google(self, prompt: str, model: str, max_tokens: int) -> Tuple[str, Dict]:
        """Chama API do Google Gemini (nova API) e retorna resposta com informações de tokens"""
        system_message = None
        if hasattr(self, '_current_system_message'):
            system_message = self._current_system_message
            delattr(self, '_current_system_message')
        
        temperature = 0.3
        
        # Usar a API key armazenada na configuração
        api_key = getattr(self, 'google_api_key', None)
        if not api_key:
            raise Exception("API key do Google não configurada")
        
        client = genai.Client(api_key=api_key)
        
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            system_instruction=system_message
        )
        
        # Log do payload para debug
        logger.debug("[Google Gemini] Payload enviado:")
        logger.debug(pprint.pformat({
            "model": model,
            "system_instruction": system_message,
            "prompt": prompt,
            "max_output_tokens": max_tokens,
            "temperature": temperature
        }))
        
        try:
            response = client.models.generate_content(
                model=model,
                config=config,
                contents=prompt
            )
            logger.debug(f"[Google Gemini] Resposta bruta: {response!r}")
            response_text = getattr(response, 'text', None)
            logger.debug(f"[Google Gemini] response.text: {response_text!r}")
            if response_text is None:
                response_text = ''
            
            # Capturar dados de uso da API Google Gemini
            usage_data = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_metadata = response.usage_metadata
                def safe_int(val):
                    return int(val) if isinstance(val, int) and val is not None else 0
                usage_data = {
                    'input_tokens': safe_int(getattr(usage_metadata, 'prompt_token_count', 0)),
                    'output_tokens': safe_int(getattr(usage_metadata, 'candidates_token_count', 0)),
                    'total_tokens': safe_int(getattr(usage_metadata, 'total_token_count', 0)),
                    'cached_content_tokens': safe_int(getattr(usage_metadata, 'cached_content_token_count', 0))
                }
                logger.debug(f"[Google Gemini] Tokens capturados da API:")
                logger.debug(f"  Input: {usage_data['input_tokens']}")
                logger.debug(f"  Output: {usage_data['output_tokens']}")
                logger.debug(f"  Total: {usage_data['total_tokens']}")
                logger.debug(f"  Cached: {usage_data['cached_content_tokens']}")
            
            # Salvar resposta completa para debug
            debug_data = {
                "timestamp": datetime.now().isoformat(),
                "provider": "google",
                "model": model,
                "system_message": system_message,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "request_params": {
                    "model": model,
                    "system_instruction": system_message,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                "response_text": response_text,
                "usage_data": usage_data,
                "raw_response": str(response)
            }
            with open("debug_response_google.json", "w", encoding="utf-8") as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)
            
            # Se não conseguiu capturar da API, usar estimativa
            if not usage_data:
                logger.warning("[Google Gemini] Não foi possível capturar tokens da API, usando estimativa")
                safe_prompt = prompt if prompt is not None else ""
                safe_response = response_text if response_text is not None else ""
                usage_data = {
                    'input_tokens': self.token_counter.count_tokens(safe_prompt, model),
                    'output_tokens': self.token_counter.count_tokens(safe_response, model),
                    'total_tokens': 0,
                    'cached_content_tokens': 0
                }
                usage_data['total_tokens'] = usage_data['input_tokens'] + usage_data['output_tokens']
            
            # Calcular custo usando dados da API se disponíveis
            cost_info = self.token_usage_manager.calculate_cost_from_api_response(usage_data, model)
            cost_info['api_provided'] = usage_data is not None and usage_data.get('input_tokens', 0) > 0
            cost_info['estimated'] = not cost_info['api_provided']
            
            # Formatar para exibição
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return response_text, {
                'success': True,
                'model_used': model,
                'provider': 'google',
                'usage_data': usage_data,
                'cost_info': cost_info,
                'display_info': display_info
            }
            
        except Exception as e:
            logger.error(f"Erro na API Google: {e}")
            # Fallback com estimativa
            fallback_response = f"Erro na API Google: {str(e)}"
            cost_info = self.token_usage_manager.calculate_cost_from_estimation(prompt, fallback_response, model)
            display_info = self.token_usage_manager.format_cost_for_display(cost_info)
            
            return fallback_response, {
                'success': False,
                'model_used': model,
                'provider': 'google',
                'error': str(e),
                'cost_info': cost_info,
                'display_info': display_info
            }
    
    def _simulate_response(self, prompt: str) -> str:
        """Simula resposta quando API não está disponível"""
        return f"""
DECISÃO

[Minuta gerada automaticamente baseada no prompt fornecido]

{prompt[:200]}...

[Conteúdo simulado - configure as APIs de IA para uso real]

Assinado eletronicamente,
[Assessor]
Data: {datetime.now().strftime('%d/%m/%Y')}
        """.strip()
    
    def get_available_models(self) -> List[str]:
        """Retorna lista de modelos disponíveis baseada na configuração"""
        return get_all_models()
    
    def get_models_by_provider(self, provider: str) -> List[str]:
        """Retorna lista de modelos de um fabricante específico"""
        from models_config import get_models_by_provider
        return get_models_by_provider(provider)
    
    def get_model_info(self, model: str) -> Dict:
        """Retorna informações detalhadas de um modelo"""
        return get_model_info(model)

    def _get_model_instructions(self, model_id: str) -> str:
        """Obtém as instruções gerais do sistema"""
        try:
            # Verificar se estamos no contexto da aplicação Flask
            from flask import current_app
            from sqlalchemy import text
            if current_app and current_app.app_context():
                # Usar query SQL direta para evitar conflitos de SQLAlchemy
                db = current_app.extensions['sqlalchemy'].db
                
                # Buscar instrução geral
                result = db.session.execute(
                    text("SELECT instructions FROM general_instructions LIMIT 1")
                ).fetchone()
                
                if result:
                    return result[0]
                
                return ""
            else:
                return ""
        except Exception as e:
            logger.warning(f"Erro ao obter instruções gerais: {e}")
            return ""

# Instância global
ai_manager = AIManager() 