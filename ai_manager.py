import os
import tiktoken
import openai
import anthropic
import google.generativeai as genai
from typing import Dict, List, Tuple, Optional
import json
import logging
from datetime import datetime
from models_config import MODELS_CONFIG, get_all_models, get_model_info, get_provider_for_model

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                    encoder_type = MODELS_CONFIG[provider]["encoder"]
                    
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
        
        # Configurar APIs
        self.openai_client = None
        self.anthropic_client = None
        self.google_genai = None
        
        self._setup_clients()
    
    def _setup_clients(self):
        """Configura os clientes das APIs"""
        # OpenAI
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if openai_api_key:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                logger.info("Cliente OpenAI configurado")
            except Exception as e:
                logger.error(f"Erro ao configurar OpenAI: {e}")
        
        # Anthropic
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(
                    api_key=anthropic_api_key,
                    timeout=600.0  # 10 minutos de timeout
                )
                logger.info("Cliente Anthropic configurado")
            except Exception as e:
                logger.error(f"Erro ao configurar Anthropic: {e}")
        
        # Google
        google_api_key = os.getenv('GOOGLE_API_KEY')
        if google_api_key:
            try:
                genai.configure(api_key=google_api_key)
                self.google_genai = genai
                logger.info("Cliente Google configurado")
            except Exception as e:
                logger.error(f"Erro ao configurar Google: {e}")
    
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
            Tuple[str, Dict]: (resposta, metadados com contagem de tokens)
        """
        tokens_info = {
            'request_tokens': self.count_request_tokens(prompt, model),
            'response_tokens': 0,
            'total_tokens': 0,
            'model_used': model,
            'success': False,
            'error': None
        }
        
        try:
            # Obter informações do modelo
            model_info = get_model_info(model)
            if not model_info:
                tokens_info['error'] = f"Modelo '{model}' não encontrado na configuração"
                return f"Erro: Modelo '{model}' não configurado", tokens_info
            
            provider = model_info["provider"]
            
            # Usar max_tokens do modelo se disponível
            if max_tokens == 2000:  # Valor padrão
                max_tokens = model_info.get("max_tokens", 2000)
            
            if provider == "openai" and self.openai_client:
                response = self._call_openai(prompt, model, max_tokens)
                tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                tokens_info['success'] = True
                return response, tokens_info
                
            elif provider == "anthropic" and self.anthropic_client:
                response = self._call_anthropic(prompt, model, max_tokens)
                tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                tokens_info['success'] = True
                return response, tokens_info
                
            elif provider == "google" and self.google_genai:
                response = self._call_google(prompt, model, max_tokens)
                tokens_info['response_tokens'] = self.count_response_tokens(response, model)
                tokens_info['total_tokens'] = tokens_info['request_tokens'] + tokens_info['response_tokens']
                tokens_info['success'] = True
                return response, tokens_info
                
            else:
                # Fallback: simulação
                api_name = model_info.get("provider_name", provider)
                tokens_info['error'] = f"API {api_name} não configurada para modelo {model}"
                return self._simulate_response(prompt), tokens_info
                
        except Exception as e:
            tokens_info['error'] = str(e)
            logger.error(f"Erro ao gerar resposta: {e}")
            # Manter os tokens de request mesmo em caso de erro
            tokens_info['total_tokens'] = tokens_info['request_tokens']
            return f"Erro na geração: {str(e)}", tokens_info
    
    def _call_openai(self, prompt: str, model: str, max_tokens: int) -> str:
        """Chama API da OpenAI"""
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def _call_anthropic(self, prompt: str, model: str, max_tokens: int) -> str:
        """Chama API da Anthropic com streaming para requisições longas"""
        try:
            # Tentar primeiro sem streaming
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            error_msg = str(e)
            if "Streaming is strongly recommended" in error_msg or "longer than 10 minutes" in error_msg:
                logger.info(f"Usando streaming para modelo {model} devido a requisição longa")
                return self._call_anthropic_streaming(prompt, model, max_tokens)
            else:
                raise e
    
    def _call_anthropic_streaming(self, prompt: str, model: str, max_tokens: int) -> str:
        """Chama API da Anthropic com streaming"""
        try:
            full_response = ""
            with self.anthropic_client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for message in stream:
                    if message.type == "content_block_delta":
                        full_response += message.delta.text
                    elif message.type == "message_stop":
                        break
            
            return full_response
        except Exception as e:
            logger.error(f"Erro no streaming da Anthropic: {e}")
            raise e
    
    def _call_google(self, prompt: str, model: str, max_tokens: int) -> str:
        """Chama API do Google"""
        model_obj = self.google_genai.GenerativeModel(model)
        response = model_obj.generate_content(prompt)
        return response.text
    
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

# Instância global
ai_manager = AIManager() 