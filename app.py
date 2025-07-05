from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
import re
import json
import argparse
import logging
from ai_manager import ai_manager
from models_config import get_all_models, get_model_info
import requests
from datetime import date, timedelta
from cryptography.fernet import Fernet
import base64
import urllib3
import io
import PyPDF2
import pdfplumber
from bs4 import BeautifulSoup

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///diria.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensões
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Filtros personalizados para templates
@app.template_filter('from_json')
def from_json_filter(value):
    """Filtro para converter string JSON em objeto Python"""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None

# Desabilitar avisos de SSL para a API do Balcão Jus
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BalcaoJusAPI:
    def __init__(self):
        self.base_url = "https://balcaojus.trf2.jus.br/balcaojus/api/v1"
        self.session = requests.Session()
        self.token = None
    
    def autenticar(self, username: str, password: str) -> dict:
        """Autentica no Balcão Jus e obtém token"""
        url = f"{self.base_url}/autenticar"
        data = {
            "username": username,
            "password": password
        }
        
        response = self.session.post(url, json=data, verify=False)
        response.raise_for_status()
        
        result = response.json()
        if "id_token" in result:
            self.token = result["id_token"]
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json"
            })
        
        return result
    
    def buscar_movimentos_processo(self, numero_processo: str, sistema: str) -> dict:
        """Busca movimentos de um processo específico"""
        url = f"{self.base_url}/processo/{numero_processo}/consultar"
        params = {"sistema": sistema}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def obter_jwt_peca(self, numero_processo: str, id_peca: str, sistema: str) -> str:
        """Obtém JWT para download de uma peça"""
        url = f"{self.base_url}/processo/{numero_processo}/peca/{id_peca}/pdf"
        params = {"sistema": sistema}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        result = response.json()
        return result.get("jwt")
    
    def download_peca(self, jwt: str, numero_processo: str, id_peca: str) -> bytes:
        """Faz download do conteúdo da peça"""
        url = f"{self.base_url}/download/{jwt}/{numero_processo}-peca-{id_peca}.pdf"
        
        response = self.session.get(url)
        response.raise_for_status()
        return response.content

def extrair_texto_conteudo(conteudo_bytes: bytes, formato: str = 'pdf') -> str:
    """
    Extrai texto de conteúdo PDF ou HTML
    
    Args:
        conteudo_bytes: Conteúdo em bytes
        formato: 'pdf' ou 'html'
    
    Returns:
        Texto extraído ou mensagem de erro
    """
    try:
        if formato.lower() == 'pdf':
            return extrair_texto_pdf(conteudo_bytes)
        elif formato.lower() == 'html':
            return extrair_texto_html(conteudo_bytes)
        else:
            return f"Formato não suportado: {formato}"
    except Exception as e:
        return f"Erro ao extrair texto: {str(e)}"

def extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """
    Extrai texto de um PDF usando múltiplas bibliotecas para melhor resultado
    """
    texto = ""
    
    # Tentar com pdfplumber primeiro (melhor para PDFs complexos)
    try:
        with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina + "\n"
        
        if texto.strip():
            return texto.strip()
    except Exception as e:
        print(f"pdfplumber falhou: {e}")
    
    # Fallback para PyPDF2
    try:
        pdf_file = io.BytesIO(conteudo_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        for pagina in pdf_reader.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto += texto_pagina + "\n"
        
        return texto.strip()
    except Exception as e:
        return f"Erro ao extrair texto do PDF: {str(e)}"

def extrair_texto_html(conteudo_bytes: bytes) -> str:
    """
    Extrai texto de conteúdo HTML seguindo regras específicas para atos judiciais
    """
    try:
        # Tentar diferentes encodings para preservar acentos
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        html_content = None
        
        for encoding in encodings:
            try:
                html_content = conteudo_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if html_content is None:
            # Fallback: usar utf-8 com errors='replace'
            html_content = conteudo_bytes.decode('utf-8', errors='replace')
        
        # Parse HTML com encoding explícito
        soup = BeautifulSoup(html_content, 'html.parser', from_encoding='utf-8')
        
        # Remover scripts e estilos
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Remover header e footer
        for header in soup.find_all("header"):
            header.decompose()
        for footer in soup.find_all("footer"):
            footer.decompose()
        
        # Encontrar o elemento article
        article = soup.find("article")
        if article:
            # Lógica específica para article com seções (mantida como estava)
            secoes = article.find_all("section")
            if secoes:
                texto_extraido = []
                
                for secao in secoes:
                    # Verificar se a seção deve ser ignorada baseada nos atributos data-nome
                    data_nome = secao.get('data-nome', '')
                    secoes_ignorar = ['endereco', 'identificacao_processo', 'partes', 'assinaturas', 'notas']
                    
                    if data_nome in secoes_ignorar:
                        continue  # Ignorar esta seção
                    
                    # Extrair texto dos parágrafos dentro da seção
                    paragrafos = secao.find_all('p')
                    for paragrafo in paragrafos:
                        # Usar string diretamente para preservar caracteres especiais
                        texto_paragrafo = paragrafo.get_text(separator=' ', strip=True)
                        if texto_paragrafo:  # Só adicionar se não estiver vazio
                            texto_extraido.append(texto_paragrafo)
                
                # Juntar todos os parágrafos com quebras de linha
                texto_final = '\n\n'.join(texto_extraido)
                
                # Limpar texto (remover espaços extras, mas preservar quebras de linha)
                linhas = []
                for linha in texto_final.split('\n'):
                    linha_limpa = ' '.join(linha.split())  # Remove espaços múltiplos
                    if linha_limpa:  # Só adicionar linhas não vazias
                        linhas.append(linha_limpa)
                
                texto_final = '\n\n'.join(linhas)
                
                if texto_final:
                    return texto_final
                else:
                    # Se não encontrou texto nas seções, usar fallback
                    return _extrair_texto_completo_html(soup)
            else:
                # Se não há seções no article, usar fallback
                return _extrair_texto_completo_html(soup)
        else:
            # Elemento article não encontrado, usar fallback para extrair todo o texto
            return _extrair_texto_completo_html(soup)
        
    except Exception as e:
        return f"Erro ao extrair texto do HTML: {str(e)}"

def _extrair_texto_completo_html(soup) -> str:
    """
    Função auxiliar para extrair todo o texto do HTML quando não há article/sections
    """
    try:
        # Remover elementos que geralmente não contêm conteúdo relevante
        elementos_remover = ['script', 'style', 'nav', 'aside', 'header', 'footer']
        for elemento in elementos_remover:
            for tag in soup.find_all(elemento):
                tag.decompose()
        
        # Extrair texto de todos os elementos de texto
        texto_extraido = []
        
        # Buscar por parágrafos primeiro (mais comum em documentos)
        paragrafos = soup.find_all('p')
        if paragrafos:
            for paragrafo in paragrafos:
                texto = paragrafo.get_text(separator=' ', strip=True)
                if texto:
                    texto_extraido.append(texto)
        
        # Se não encontrou parágrafos, buscar por divs com texto
        if not texto_extraido:
            divs = soup.find_all('div')
            for div in divs:
                # Verificar se o div contém texto direto (não apenas elementos filhos)
                if div.string and div.string.strip():
                    texto = div.get_text(separator=' ', strip=True)
                    if texto and len(texto) > 10:  # Filtrar textos muito curtos
                        texto_extraido.append(texto)
        
        # Se ainda não encontrou, extrair todo o texto do body
        if not texto_extraido:
            body = soup.find('body')
            if body:
                texto = body.get_text(separator='\n', strip=True)
                if texto:
                    # Dividir em linhas e limpar
                    linhas = []
                    for linha in texto.split('\n'):
                        linha_limpa = ' '.join(linha.split())
                        if linha_limpa and len(linha_limpa) > 5:  # Filtrar linhas muito curtas
                            linhas.append(linha_limpa)
                    texto_extraido = linhas
        
        # Juntar e limpar o texto final
        if texto_extraido:
            texto_final = '\n\n'.join(texto_extraido)
            
            # Limpar texto (remover espaços extras, mas preservar quebras de linha)
            linhas = []
            for linha in texto_final.split('\n'):
                linha_limpa = ' '.join(linha.split())  # Remove espaços múltiplos
                if linha_limpa:  # Só adicionar linhas não vazias
                    linhas.append(linha_limpa)
            
            texto_final = '\n\n'.join(linhas)
            return texto_final
        else:
            return "Nenhum texto encontrado no HTML"
            
    except Exception as e:
        return f"Erro ao extrair texto completo do HTML: {str(e)}"

def detectar_formato_conteudo(conteudo_bytes: bytes) -> str:
    """
    Detecta o formato do conteúdo baseado nos primeiros bytes
    """
    # Verificar assinatura do PDF
    if conteudo_bytes.startswith(b'%PDF'):
        return 'pdf'
    
    # Verificar se é HTML
    try:
        inicio = conteudo_bytes[:1000].decode('utf-8', errors='ignore').lower()
        if '<html' in inicio or '<!doctype' in inicio:
            return 'html'
    except:
        pass
    
    # Padrão é PDF
    return 'pdf'

# Modelos do banco de dados
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    first_login = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_authenticated(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)

class Prompt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    ai_model = db.Column(db.String(50), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class UsageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    tokens_used = db.Column(db.Integer, default=0)
    request_tokens = db.Column(db.Integer, default=0)
    response_tokens = db.Column(db.Integer, default=0)
    model_used = db.Column(db.String(50), nullable=True)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('logs', lazy=True))

class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class GeneralInstructions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instructions = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), unique=True, nullable=False)  # openai, anthropic, google
    api_key = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<APIKey {self.provider}>'

class EprocCredentials(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.Text, nullable=False)  # Criptografado
    password = db.Column(db.Text, nullable=False)  # Criptografado
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<EprocCredentials {"Ativo" if self.is_active else "Inativo"}>'

class DollarRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rate = db.Column(db.Float, nullable=False)  # Taxa de câmbio USD/BRL
    date = db.Column(db.Date, nullable=False)   # Data da cotação
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<DollarRate {self.date}: {self.rate}>'



class AIModel(db.Model):
    """Modelo para armazenar modelos de IA dinamicamente"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # ID interno
    provider = db.Column(db.String(50), nullable=False)  # openai, anthropic, google
    model_id = db.Column(db.String(100), unique=True, nullable=False)  # ID real da API
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_tokens = db.Column(db.Integer, default=32768)
    context_window = db.Column(db.Integer, default=32768)
    price_input = db.Column(db.Float, default=0.0)  # Preço por MTok entrada
    price_output = db.Column(db.Float, default=0.0)  # Preço por MTok saída
    is_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<AIModel {self.display_name} ({self.provider})>'

class DebugRequest(db.Model):
    """Modelo para armazenar requisições de debug da IA"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # generate_minuta, adjust_minuta
    request_data = db.Column(db.Text, nullable=False)  # JSON da requisição
    response_data = db.Column(db.Text, nullable=False)  # JSON da resposta
    prompt_used = db.Column(db.Text, nullable=True)  # Prompt final usado
    model_used = db.Column(db.String(100), nullable=True)
    tokens_info = db.Column(db.Text, nullable=True)  # JSON com info de tokens
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    user = db.relationship('User', backref=db.backref('debug_requests', lazy=True))
    
    def __repr__(self):
        return f'<DebugRequest {self.action} by {self.user_id} at {self.created_at}>'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def get_app_config(key, default=None):
    """Obtém uma configuração da aplicação"""
    config = AppConfig.query.filter_by(key=key).first()
    return config.value if config else default

def set_app_config(key, value, description=None):
    """Define uma configuração da aplicação"""
    config = AppConfig.query.filter_by(key=key).first()
    if config:
        config.value = value
        if description:
            config.description = description
    else:
        config = AppConfig(key=key, value=value, description=description)
        db.session.add(config)
    db.session.commit()

def get_default_ai_model():
    """Obtém o modelo de IA padrão da aplicação"""
    return get_app_config('default_ai_model', 'gemini-2.5-pro')

def get_general_instructions():
    """Obtém as instruções gerais"""
    general = GeneralInstructions.query.first()
    return general.instructions if general else ""

def get_api_key(provider):
    """Obtém a chave de API de um provedor específico"""
    api_key = APIKey.query.filter_by(provider=provider, is_active=True).first()
    return api_key.api_key if api_key else None

def set_api_key(provider, api_key_value):
    """Define a chave de API de um provedor"""
    existing = APIKey.query.filter_by(provider=provider).first()
    if existing:
        existing.api_key = api_key_value
        existing.updated_at = datetime.now(timezone.utc)
    else:
        new_key = APIKey(provider=provider, api_key=api_key_value)
        db.session.add(new_key)
    db.session.commit()

def get_all_api_keys():
    """Obtém todas as chaves de API"""
    return APIKey.query.all()

# Funções para criptografia das credenciais do eproc
def get_encryption_key():
    """Obtém a chave de criptografia baseada na SECRET_KEY do Flask"""
    secret_key = app.config['SECRET_KEY']
    # Usar os primeiros 32 bytes da SECRET_KEY para o Fernet
    key = base64.urlsafe_b64encode(secret_key.encode()[:32].ljust(32, b'0'))
    return key

def encrypt_text(text):
    """Criptografa um texto usando a chave do Flask"""
    if not text:
        return ""
    key = get_encryption_key()
    f = Fernet(key)
    return f.encrypt(text.encode()).decode()

def decrypt_text(encrypted_text):
    """Descriptografa um texto usando a chave do Flask"""
    if not encrypted_text:
        return ""
    try:
        key = get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_text.encode()).decode()
    except Exception as e:
        print(f"Erro ao descriptografar: {e}")
        return ""

def get_eproc_credentials():
    """Obtém as credenciais do eproc (descriptografadas)"""
    credentials = EprocCredentials.query.filter_by(is_active=True).first()
    if credentials:
        return {
            'login': decrypt_text(credentials.login),
            'password': decrypt_text(credentials.password),
            'is_active': credentials.is_active
        }
    return None

def set_eproc_credentials(login, password):
    """Define as credenciais do eproc (criptografadas)"""
    # Desativar credenciais existentes
    existing = EprocCredentials.query.filter_by(is_active=True).first()
    if existing:
        existing.is_active = False
        existing.updated_at = datetime.now(timezone.utc)
    
    # Criar novas credenciais
    new_credentials = EprocCredentials(
        login=encrypt_text(login),
        password=encrypt_text(password),
        is_active=True
    )
    db.session.add(new_credentials)
    db.session.commit()

def test_eproc_credentials(login, password):
    """Testa as credenciais do eproc (simulado por enquanto)"""
    # Por enquanto, apenas valida se os campos não estão vazios
    if not login or not password:
        return False, "Login e senha são obrigatórios"
    
    # Simular teste de credenciais
    # Em implementação real, aqui seria feita a chamada para a API do balcão jus
    return True, "Credenciais válidas (teste simulado)"

def get_dollar_rate():
    """
    Obtém a cotação atual do dólar.
    Se não houver cotação para hoje, busca da API do Banco Central.
    """
    today = date.today()
    
    # Verificar se já temos cotação para hoje
    rate_record = DollarRate.query.filter_by(date=today).first()
    if rate_record:
        return rate_record.rate
    
    # Se não temos, buscar da API do Banco Central
    try:
        # Data de ontem (API do BC usa data anterior)
        yesterday = today - timedelta(days=1)
        date_str = yesterday.strftime('%m-%d-%Y')
        
        url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{date_str}'&$top=100&$format=json&$select=cotacaoVenda"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('value') and len(data['value']) > 0:
            rate = data['value'][0]['cotacaoVenda']
            
            # Salvar no banco
            new_rate = DollarRate(rate=rate, date=today)
            db.session.add(new_rate)
            db.session.commit()
            
            return rate
        else:
            # Fallback para cotação fixa se API falhar
            return 5.5
    except Exception as e:
        print(f"Erro ao buscar cotação do dólar: {e}")
        # Fallback para cotação fixa
        return 5.5

def get_model_status(model_id):
    """Obtém o status de um modelo específico"""
    try:
        model = AIModel.query.filter_by(model_id=model_id).first()
        return model.is_enabled if model else False
    except Exception as e:
        print(f"⚠️  Erro ao buscar modelo no banco: {e}")
        return False

def set_model_status(model_id, is_enabled):
    """Define o status de um modelo"""
    try:
        model = AIModel.query.filter_by(model_id=model_id).first()
        if model:
            model.is_enabled = is_enabled
            model.updated_at = datetime.now(timezone.utc)
            db.session.commit()
        else:
            print(f"⚠️  Modelo {model_id} não encontrado no banco")
    except Exception as e:
        print(f"⚠️  Erro ao atualizar status do modelo: {e}")

def get_enabled_models():
    """Obtém lista de modelos habilitados"""
    try:
        models = AIModel.query.filter_by(is_enabled=True).all()
        return [model.model_id for model in models]
    except Exception as e:
        print(f"⚠️  Erro ao carregar modelos habilitados: {e}")
        return []

def get_all_models_with_status():
    """Retorna todos os modelos com status de habilitação (apenas do banco)"""
    try:
        with app.app_context():
            models = AIModel.query.all()
            models_with_status = []
            
            for model in models:
                models_with_status.append({
                    'id': model.model_id,
                    'name': model.display_name,
                    'provider': model.provider,
                    'is_enabled': model.is_enabled,
                    'description': model.description or '',
                    'max_tokens': model.max_tokens,
                    'context_window': model.context_window,
                    'cost_per_1k_input': model.price_input,
                    'cost_per_1k_output': model.price_output
                })
            
            return models_with_status
    except Exception as e:
        print(f"⚠️  Erro ao carregar modelos do banco: {e}")
        return []

def get_models_for_dropdown():
    """Retorna modelos formatados para dropdowns (apenas do banco)"""
    try:
        with app.app_context():
            models = AIModel.query.filter_by(is_enabled=True).all()
            return [{
                'id': model.model_id,
                'name': model.display_name,
                'provider': model.provider,
                'description': model.description
            } for model in models]
    except Exception as e:
        print(f"⚠️  Erro ao carregar modelos do banco: {e}")
        return []  # Retornar lista vazia se não conseguir acessar banco

def get_default_model():
    """Retorna modelo padrão do banco ou configuração"""
    try:
        with app.app_context():
            default_model = AIModel.query.filter_by(is_enabled=True).first()
            if default_model:
                return default_model.model_id
    except:
        pass
    return get_app_config('default_ai_model', 'gemini-2.5-pro')

def get_model_info_safe(model_id: str) -> dict:
    """Busca modelo apenas do banco"""
    try:
        with app.app_context():
            model = AIModel.query.filter_by(model_id=model_id, is_enabled=True).first()
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

def format_cost_for_user(cost_usd):
    """
    Formata o custo para exibição ao usuário em Real
    """
    if cost_usd is None or cost_usd <= 0:
        return "R$ 0,00"
    
    rate = get_dollar_rate()
    cost_brl = cost_usd * rate
    
    # Arredondar para cima em no máximo duas casas decimais
    cost_brl = round(cost_brl + 0.005, 2)  # +0.005 para arredondar para cima
    
    return f"R$ {cost_brl:.2f}".replace('.', ',')

def format_cost_for_admin(cost_usd):
    """
    Formata o custo para exibição ao admin (USD e BRL)
    """
    if cost_usd is None or cost_usd <= 0:
        return {
            'usd': '$0.00',
            'brl': 'R$ 0,00',
            'rate': 0,
            'rate_date': None
        }
    
    rate = get_dollar_rate()
    cost_brl = cost_usd * rate
    
    # Buscar data da cotação
    rate_record = DollarRate.query.order_by(DollarRate.date.desc()).first()
    rate_date = rate_record.date if rate_record else None
    
    return {
        'usd': f"${cost_usd:.6f}",
        'brl': f"R$ {cost_brl:.2f}".replace('.', ','),
        'rate': rate,
        'rate_date': rate_date.strftime('%d/%m/%Y') if rate_date else 'N/A'
    }

def format_instructions_for_provider(instructions, provider, model_id):
    """Formata as instruções de acordo com o provedor da API"""
    if not instructions:
        return ""
    
    # Para todos os provedores, usar as instruções como system message
    if provider in ["openai", "anthropic", "google"]:
        return {
            "system_message": instructions.instructions,
            "user_prefix": ""
        }
    
    return ""

def format_conclusion_for_provider(instructions, provider):
    """Formata a conclusão de acordo com o provedor da API"""
    # Não há mais conclusão separada, tudo está nas instruções
    return ""

def extrair_pecas_movimentos_balcaojus(json_movimentos):
    """
    Processa o JSON de resposta do Balcão Jus e retorna uma lista de peças vinculadas a movimentos.
    Cada item da lista contém: evento, data, descricao, lista de peças (com id, descricao, tipo, mimetype, data, etc)
    """
    if not json_movimentos or 'value' not in json_movimentos:
        return []
    value = json_movimentos['value']
    movimentos = value.get('movimento', [])
    documentos = value.get('documento', [])
    # Indexar documentos por id para busca rápida
    doc_by_id = {doc['idDocumento']: doc for doc in documentos}
    resultado = []
    for mov in movimentos:
        evento = mov.get('identificadorMovimento')
        data = mov.get('dataHora')
        descricao_mov = mov.get('movimentoLocal', {}).get('descricao', '')
        pecas = []
        for id_doc in mov.get('idDocumentoVinculado', []):
            doc = doc_by_id.get(id_doc)
            if doc:
                pecas.append({
                    'id': doc['idDocumento'],
                    'descricao': doc.get('descricao', ''),
                    'tipo': doc.get('tipoDocumento', ''),
                    'mimetype': doc.get('mimetype', ''),
                    'data': doc.get('dataHora', ''),
                    'movimento': doc.get('movimento', ''),
                    'rotulo': doc.get('outroParametro', {}).get('rotulo', ''),
                    'tamanho': doc.get('outroParametro', {}).get('tamanho', ''),
                })
        if pecas:
            resultado.append({
                'evento': evento,
                'data': data,
                'descricao': descricao_mov,
                'pecas': pecas
            })
    return resultado

def save_debug_request(action, request_data, response_data, prompt_used=None, model_used=None, tokens_info=None, success=True, error_message=None):
    """Salva uma requisição de debug no banco de dados"""
    try:
        # Manter apenas as 20 últimas requisições por usuário
        user_id = current_user.id if current_user.is_authenticated else None
        
        if user_id:
            # Contar requisições existentes do usuário
            count = DebugRequest.query.filter_by(user_id=user_id).count()
            
            if count >= 20:
                # Remover as mais antigas até ficar com 19 (para adicionar a nova)
                excess_count = count - 19
                oldest_requests = DebugRequest.query.filter_by(user_id=user_id).order_by(DebugRequest.created_at.asc()).limit(excess_count).all()
                for old_request in oldest_requests:
                    db.session.delete(old_request)
        
        # Criar nova requisição de debug
        debug_request = DebugRequest(
            user_id=user_id,
            action=action,
            request_data=json.dumps(request_data, ensure_ascii=False, indent=2),
            response_data=json.dumps(response_data, ensure_ascii=False, indent=2),
            prompt_used=prompt_used,
            model_used=model_used,
            tokens_info=json.dumps(tokens_info, ensure_ascii=False, indent=2) if tokens_info else None,
            success=success,
            error_message=error_message
        )
        
        db.session.add(debug_request)
        db.session.commit()
        
        return debug_request.id
        
    except Exception as e:
        app.logger.error(f"Erro ao salvar debug request: {str(e)}")
        db.session.rollback()
        return None

def get_debug_requests(limit=10):
    """Retorna as últimas requisições de debug"""
    try:
        requests = DebugRequest.query.order_by(DebugRequest.created_at.desc()).limit(limit).all()
        return requests
    except Exception as e:
        app.logger.error(f"Erro ao buscar debug requests: {str(e)}")
        return []

def get_user_debug_requests(user_id, limit=20):
    """Retorna as últimas requisições de debug de um usuário específico"""
    try:
        requests = DebugRequest.query.filter_by(user_id=user_id).order_by(DebugRequest.created_at.desc()).limit(limit).all()
        return requests
    except Exception as e:
        app.logger.error(f"Erro ao buscar debug requests do usuário: {str(e)}")
        return []

# Rotas
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Email ou senha inválidos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal - agora usa a versão eproc"""
    prompts = Prompt.query.all()
    return render_template('dashboard_eproc.html', prompts=prompts)

@app.route('/dashboardb')
@login_required
def dashboard_eproc():
    """Dashboard alternativo com integração eproc - mantido como backup"""
    prompts = Prompt.query.all()
    return render_template('dashboard_eproc.html', prompts=prompts)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Senha atual incorreta.', 'error')
        elif new_password != confirm_password:
            flash('As senhas não coincidem.', 'error')
        elif len(new_password) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.', 'error')
        else:
            current_user.set_password(new_password)
            current_user.first_login = False
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

@app.route('/generate_minuta', methods=['POST'])
@login_required
def generate_minuta():
    try:
        data = request.get_json()
        
        # Validação dos campos obrigatórios
        if not data.get('pecas_processuais') or len(data['pecas_processuais']) == 0:
            return jsonify({'error': 'Pelo menos uma peça processual é obrigatória.'}), 400
        
        if not data.get('como_decidir'):
            return jsonify({'error': 'O campo "Como decidir" é obrigatório.'}), 400
        
        # Limpar número do processo (apenas números)
        numero_processo = data.get('numero_processo', '')
        if numero_processo:
            numero_processo = re.sub(r'[^\d]', '', numero_processo)
        
        # Obter o prompt selecionado
        prompt_id = data.get('prompt_id')
        if prompt_id:
            prompt = db.session.get(Prompt, int(prompt_id))
        else:
            prompt = Prompt.query.filter_by(is_default=True).first()
        
        if not prompt:
            return jsonify({'error': 'Nenhum prompt encontrado.'}), 400
        
        # Usar o modelo de IA selecionado pelo usuário
        ai_model_id = data.get('ai_model_id')
        if not ai_model_id:
            return jsonify({'error': 'Modelo de IA não selecionado.'}), 400
        
        # Verificar se o modelo está habilitado
        if not get_model_status(ai_model_id):
            return jsonify({'error': f'Modelo {ai_model_id} não está habilitado no sistema.'}), 400
        
        # Preparar dados para o prompt
        pecas_texto = ""
        for peca in data.get('pecas_processuais', []):
            nome_peca = peca.get('nome', '').strip()
            conteudo_peca = peca.get('conteudo', '').strip()
            
            if nome_peca and conteudo_peca:
                # Formatar como grupo estruturado
                pecas_texto += f"\n{'-' * 50}\n"
                pecas_texto += f"{nome_peca.upper()}:\n"
                pecas_texto += f"{'-' * 50}\n"
                pecas_texto += f"{conteudo_peca}\n"
                pecas_texto += f"{'-' * 50}\n"
        
        # Se não há peças estruturadas, usar formato antigo como fallback
        if not pecas_texto.strip():
            for peca in data.get('pecas_processuais', []):
                pecas_texto += f"\n- {peca.get('nome', '')}: {peca.get('conteudo', '')}\n"
        
        # Substituir placeholders no prompt
        prompt_content = prompt.content
        prompt_content = prompt_content.replace('{{numero_processo}}', numero_processo if numero_processo else 'Não informado')
        prompt_content = prompt_content.replace('{{pecas_processuais}}', pecas_texto)
        prompt_content = prompt_content.replace('{{como_decidir}}', data.get('como_decidir', ''))
        prompt_content = prompt_content.replace('{{fundamentos}}', data.get('fundamentos', ''))
        prompt_content = prompt_content.replace('{{vedacoes}}', data.get('vedacoes', ''))
        
        # Gerar resposta usando IA com o modelo selecionado
        minuta, tokens_info = ai_manager.generate_response(
            prompt=prompt_content,
            model=ai_model_id,
            max_tokens=2000
        )
        
        # Preparar resposta
        response_data = {
            'minuta': minuta,
            'tokens_info': {
                'request_tokens': tokens_info.get('request_tokens', 0) if tokens_info else 0,
                'response_tokens': tokens_info.get('response_tokens', 0) if tokens_info else 0,
                'total_tokens': tokens_info.get('total_tokens', 0) if tokens_info else 0,
                'model_used': tokens_info.get('model_used', ai_model_id) if tokens_info else ai_model_id,
                'success': tokens_info.get('success', False) if tokens_info else False
            },
            'cost_info': tokens_info.get('display_info', {}) if tokens_info else {},
            'user_cost': format_cost_for_user(tokens_info.get('cost_info', {}).get('total_cost', 0) if tokens_info else 0)
        }
        
        # Salvar debug request
        save_debug_request(
            action='generate_minuta',
            request_data=data,
            response_data=response_data,
            prompt_used=prompt_content,
            model_used=ai_model_id,
            tokens_info=tokens_info,
            success=tokens_info.get('success', False) if tokens_info else False,
            error_message=tokens_info.get('error') if tokens_info else None
        )
        
        # Log de uso detalhado
        log = UsageLog(
            user_id=current_user.id,
            action='generate_minuta',
            tokens_used=tokens_info.get('total_tokens', 0) if tokens_info else 0,
            request_tokens=tokens_info.get('request_tokens', 0) if tokens_info else 0,
            response_tokens=tokens_info.get('response_tokens', 0) if tokens_info else 0,
            model_used=tokens_info.get('model_used', ai_model_id) if tokens_info else ai_model_id,
            success=tokens_info.get('success', False) if tokens_info else False,
            error_message=tokens_info.get('error') if tokens_info else None
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        # Salvar debug request de erro
        error_response = {'error': str(e)}
        save_debug_request(
            action='generate_minuta',
            request_data=data if 'data' in locals() else {},
            response_data=error_response,
            success=False,
            error_message=str(e)
        )
        
        # Log de erro
        log = UsageLog(
            user_id=current_user.id,
            action='generate_minuta',
            tokens_used=0,
            success=False,
            error_message=str(e)
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(error_response), 500

@app.route('/adjust_minuta', methods=['POST'])
@login_required
def adjust_minuta():
    try:
        data = request.get_json()
        
        # Validação dos campos obrigatórios
        if not data.get('adjustment_prompt'):
            return jsonify({'error': 'O prompt de ajuste é obrigatório.'}), 400
        
        if not data.get('current_content'):
            return jsonify({'error': 'O conteúdo atual é obrigatório.'}), 400
        
        # Obter o modelo de IA selecionado
        ai_model_id = data.get('model_id')
        if not ai_model_id:
            return jsonify({'error': 'Modelo de IA não selecionado.'}), 400
        
        # Verificar se o modelo está habilitado
        if not get_model_status(ai_model_id):
            return jsonify({'error': f'Modelo {ai_model_id} não está habilitado no sistema.'}), 400
        
        # Obter o prompt original (usar o primeiro prompt disponível ou default)
        prompt = Prompt.query.filter_by(is_default=True).first()
        if not prompt:
            prompt = Prompt.query.first()
        
        if not prompt:
            return jsonify({'error': 'Nenhum prompt encontrado.'}), 400
        
        # Preparar dados para o prompt de ajuste
        pecas_texto = ""
        for peca in data.get('pecas_processuais', []):
            nome_peca = peca.get('nome', '').strip()
            conteudo_peca = peca.get('conteudo', '').strip()
            
            if nome_peca and conteudo_peca:
                # Formatar como grupo estruturado
                pecas_texto += f"\n{'-' * 50}\n"
                pecas_texto += f"{nome_peca.upper()}:\n"
                pecas_texto += f"{'-' * 50}\n"
                pecas_texto += f"{conteudo_peca}\n"
                pecas_texto += f"{'-' * 50}\n"
        
        # Se não há peças estruturadas, usar formato antigo como fallback
        if not pecas_texto.strip():
            for peca in data.get('pecas_processuais', []):
                pecas_texto += f"\n- {peca.get('nome', '')}: {peca.get('conteudo', '')}\n"
        
        # Criar prompt de ajuste com histórico
        adjustment_prompt = f"""
{data.get('adjustment_prompt', '')}

MINUTA ATUAL:
{data.get('current_content', '')}

PECAS PROCESSUAIS ORIGINAIS:
{pecas_texto}

Por favor, ajuste a minuta conforme solicitado, mantendo a estrutura e formatação adequadas para um documento judicial.
"""
        
        # Gerar resposta usando IA
        minuta_ajustada, tokens_info = ai_manager.generate_response(
            prompt=adjustment_prompt,
            model=ai_model_id,
            max_tokens=2000
        )
        
        # Preparar resposta
        response_data = {
            'minuta': minuta_ajustada,
            'tokens_info': {
                'request_tokens': tokens_info.get('request_tokens', 0) if tokens_info else 0,
                'response_tokens': tokens_info.get('response_tokens', 0) if tokens_info else 0,
                'total_tokens': tokens_info.get('total_tokens', 0) if tokens_info else 0,
                'model_used': tokens_info.get('model_used', ai_model_id) if tokens_info else ai_model_id,
                'success': tokens_info.get('success', False) if tokens_info else False
            },
            'cost_info': tokens_info.get('display_info', {}) if tokens_info else {},
            'user_cost': format_cost_for_user(tokens_info.get('cost_info', {}).get('total_cost', 0) if tokens_info else 0)
        }
        
        # Salvar debug request
        save_debug_request(
            action='adjust_minuta',
            request_data=data,
            response_data=response_data,
            prompt_used=adjustment_prompt,
            model_used=ai_model_id,
            tokens_info=tokens_info,
            success=tokens_info.get('success', False) if tokens_info else False,
            error_message=tokens_info.get('error') if tokens_info else None
        )
        
        # Log de uso detalhado
        log = UsageLog(
            user_id=current_user.id,
            action='adjust_minuta',
            tokens_used=tokens_info.get('total_tokens', 0) if tokens_info else 0,
            request_tokens=tokens_info.get('request_tokens', 0) if tokens_info else 0,
            response_tokens=tokens_info.get('response_tokens', 0) if tokens_info else 0,
            model_used=tokens_info.get('model_used', ai_model_id) if tokens_info else ai_model_id,
            success=tokens_info.get('success', False) if tokens_info else False,
            error_message=tokens_info.get('error') if tokens_info else None
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(response_data)
        
    except Exception as e:
        # Salvar debug request de erro
        error_response = {'error': str(e)}
        save_debug_request(
            action='adjust_minuta',
            request_data=data if 'data' in locals() else {},
            response_data=error_response,
            success=False,
            error_message=str(e)
        )
        
        # Log de erro
        log = UsageLog(
            user_id=current_user.id,
            action='adjust_minuta',
            tokens_used=0,
            success=False,
            error_message=str(e)
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(error_response), 500

# Rotas administrativas
@app.route('/admin')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    prompts = Prompt.query.all()
    return render_template('admin_panel.html', users=users, prompts=prompts)

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            # Criar novo usuário
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            is_admin = request.form.get('is_admin') == 'on'
            
            # Validações básicas
            if not name or not email or not password:
                flash('Todos os campos são obrigatórios.', 'error')
            elif len(password) < 6:
                flash('A senha deve ter pelo menos 6 caracteres.', 'error')
            elif User.query.filter_by(email=email).first():
                flash('Este email já está em uso.', 'error')
            else:
                user = User(
                    email=email,
                    name=name,
                    is_admin=is_admin,
                    is_active=True,
                    first_login=True
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash('Usuário criado com sucesso.', 'success')
        
        elif action == 'toggle_active':
            user_id = request.form.get('user_id')
            if user_id:
                user = db.session.get(User, int(user_id))
                if user:
                    user.is_active = not user.is_active
                    db.session.commit()
                    flash(f'Usuário {"ativado" if user.is_active else "desativado"} com sucesso.', 'success')
        
        elif action == 'toggle_admin':
            user_id = request.form.get('user_id')
            if user_id:
                user = db.session.get(User, int(user_id))
                if user and user.id != current_user.id:
                    user.is_admin = not user.is_admin
                    db.session.commit()
                    flash(f'Permissão de administrador alterada para {user.name}.', 'success')
                elif user and user.id == current_user.id:
                    flash('Você não pode alterar seu próprio tipo de usuário.', 'error')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            if user_id:
                user = db.session.get(User, int(user_id))
                if user and user.id != current_user.id:
                    db.session.delete(user)
                    db.session.commit()
                    flash('Usuário excluído com sucesso.', 'success')
                elif user and user.id == current_user.id:
                    flash('Você não pode excluir sua própria conta.', 'error')
    
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/prompts', methods=['GET', 'POST'])
@login_required
def admin_prompts():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            name = request.form.get('name')
            content = request.form.get('content')
            ai_model = request.form.get('ai_model')
            is_default = request.form.get('is_default') == 'on'
            
            # Verificar se o modelo está habilitado
            if not get_model_status(ai_model):
                flash(f'Erro: Modelo {ai_model} não está habilitado no sistema.', 'error')
            else:
                if is_default:
                    # Desmarcar outros prompts como default
                    Prompt.query.update({'is_default': False})
                
                prompt = Prompt(name=name, content=content, ai_model=ai_model, is_default=is_default)
                db.session.add(prompt)
                db.session.commit()
                flash('Prompt criado com sucesso.', 'success')
            
        elif action == 'delete':
            prompt_id = request.form.get('prompt_id')
            if prompt_id:
                prompt = db.session.get(Prompt, int(prompt_id))
                db.session.delete(prompt)
                db.session.commit()
                flash('Prompt excluído com sucesso.', 'success')
        
        elif action == 'update':
            prompt_id = request.form.get('prompt_id')
            name = request.form.get('name')
            content = request.form.get('content')
            ai_model = request.form.get('ai_model')
            is_default = request.form.get('is_default') == 'on'
            
            if prompt_id:
                prompt = db.session.get(Prompt, int(prompt_id))
                if prompt:
                    # Verificar se o modelo está habilitado
                    if not get_model_status(ai_model):
                        flash(f'Erro: Modelo {ai_model} não está habilitado no sistema.', 'error')
                    else:
                        if is_default:
                            # Desmarcar outros prompts como default
                            Prompt.query.update({'is_default': False})
                        
                        prompt.name = name
                        prompt.content = content
                        prompt.ai_model = ai_model
                        prompt.is_default = is_default
                        
                        db.session.commit()
                        flash('Prompt atualizado com sucesso.', 'success')
                else:
                    flash('Prompt não encontrado.', 'error')
            else:
                flash('ID do prompt não fornecido.', 'error')
    
    prompts = Prompt.query.all()
    
    # Obter apenas modelos habilitados do sistema
    enabled_models = get_enabled_models()
    
    # Organizar modelos por fabricante
    models_by_provider = {}
    for model_id in enabled_models:
        model_info = get_model_info(model_id)
        if model_info:
            provider = model_info["provider"]
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            models_by_provider[provider].append({
                'id': model_id,
                'display_name': model_info['display_name'],
                'description': model_info['description']
            })
    
    # Variáveis dos placeholders para o template
    placeholders = {
        'numero_processo': '{{numero_processo}}',
        'pecas_processuais': '{{pecas_processuais}}',
        'como_decidir': '{{como_decidir}}',
        'fundamentos': '{{fundamentos}}',
        'vedacoes': '{{vedacoes}}'
    }
    
    return render_template('admin_prompts.html', 
                         prompts=prompts, 
                         models_by_provider=models_by_provider,
                         default_model='gemini-2.5-pro',
                         **placeholders)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    logs = UsageLog.query.order_by(UsageLog.created_at.desc()).limit(100).all()
    
    # Calcular custos estimados para cada log e total
    total_cost_usd = 0
    for log in logs:
        if log.tokens_used > 0 and log.model_used:
            from models_config import calculate_cost
            # Usar request_tokens e response_tokens se disponíveis, senão estimar
            if log.request_tokens and log.response_tokens:
                input_tokens = log.request_tokens
                output_tokens = log.response_tokens
            else:
                # Estimativa: 50% input, 50% output
                input_tokens = log.tokens_used // 2
                output_tokens = log.tokens_used - input_tokens
            
            cost_info = calculate_cost(input_tokens, output_tokens, log.model_used)
            log.estimated_cost_brl = format_cost_for_user(cost_info.get('total_cost', 0))
            total_cost_usd += cost_info.get('total_cost', 0)
        else:
            log.estimated_cost_brl = "R$ 0,00"
    
    # Calcular custo total em BRL
    total_cost_brl = format_cost_for_user(total_cost_usd)
    
    return render_template('admin_logs.html', logs=logs, total_cost_brl=total_cost_brl)

@app.route('/admin/stats')
@login_required
def admin_stats():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    # Estatísticas gerais
    total_logs = UsageLog.query.count()
    total_tokens = db.session.query(db.func.sum(UsageLog.tokens_used)).scalar() or 0
    total_requests = UsageLog.query.filter_by(action='generate_minuta').count()
    successful_requests = UsageLog.query.filter_by(action='generate_minuta', success=True).count()
    
    # Calcular custos totais estimados
    total_cost_usd = 0
    for log in UsageLog.query.filter(UsageLog.tokens_used > 0).all():
        if log.model_used:
            from models_config import calculate_cost
            cost_info = calculate_cost(log.request_tokens or 0, log.response_tokens or 0, log.model_used)
            total_cost_usd += cost_info.get('total_cost', 0)
    
    # Formatar custos para admin
    admin_cost_info = format_cost_for_admin(total_cost_usd)
    
    # Tokens por modelo
    tokens_by_model = db.session.query(
        UsageLog.model_used,
        db.func.sum(UsageLog.tokens_used).label('total_tokens'),
        db.func.count(UsageLog.id).label('count')
    ).filter(
        UsageLog.model_used.isnot(None),
        UsageLog.tokens_used > 0
    ).group_by(UsageLog.model_used).all()
    
    # Calcular custos por modelo
    model_costs = []
    for model_data in tokens_by_model:
        model_id = model_data.model_used
        total_tokens = model_data.total_tokens
        count = model_data.count
        
        # Estimar custo baseado no modelo
        from models_config import calculate_cost
        # Assumir 50% input, 50% output para estimativa
        estimated_input = total_tokens // 2
        estimated_output = total_tokens - estimated_input
        cost_info = calculate_cost(estimated_input, estimated_output, model_id)
        
        model_costs.append({
            'model': model_id,
            'total_tokens': total_tokens,
            'count': count,
            'cost_usd': cost_info.get('total_cost', 0),
            'cost_brl': format_cost_for_user(cost_info.get('total_cost', 0))
        })
    
    # Tokens por usuário
    tokens_by_user = db.session.query(
        User.name,
        db.func.sum(UsageLog.tokens_used).label('total_tokens'),
        db.func.count(UsageLog.id).label('count')
    ).join(UsageLog).filter(
        UsageLog.tokens_used > 0
    ).group_by(User.id, User.name).all()
    
    # Últimos 7 dias
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_logs = UsageLog.query.filter(
        UsageLog.created_at >= seven_days_ago
    ).count()
    
    recent_tokens = db.session.query(
        db.func.sum(UsageLog.tokens_used)
    ).filter(
        UsageLog.created_at >= seven_days_ago,
        UsageLog.tokens_used > 0
    ).scalar() or 0
    
    # Cotação atual do dólar
    current_rate = get_dollar_rate()
    latest_rate_record = DollarRate.query.order_by(DollarRate.date.desc()).first()
    
    stats = {
        'total_logs': total_logs,
        'total_tokens': total_tokens,
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
        'tokens_by_model': tokens_by_model,
        'model_costs': model_costs,
        'tokens_by_user': tokens_by_user,
        'recent_logs': recent_logs,
        'recent_tokens': recent_tokens,
        'total_cost_usd': admin_cost_info['usd'],
        'total_cost_brl': admin_cost_info['brl'],
        'current_rate': current_rate,
        'rate_date': admin_cost_info['rate_date']
    }
    
    return render_template('admin_stats.html', stats=stats)

@app.route('/api/default_model')
def get_default_model():
    """Retorna o modelo de IA padrão da aplicação"""
    return jsonify({
        'default_model': get_default_ai_model()
    })

@app.route('/api/available_models')
def get_available_models():
    """Retorna lista de modelos disponíveis (apenas habilitados do banco)"""
    try:
        models = get_models_for_dropdown()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Erro ao carregar modelos do banco de dados',
            'models': []
        })

@app.route('/admin/config', methods=['GET', 'POST'])
@login_required
def admin_config():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_default_model':
            new_default_model = request.form.get('default_ai_model')
            if new_default_model:
                set_app_config('default_ai_model', new_default_model, 'Modelo de IA padrão da aplicação')
                flash('Modelo padrão atualizado com sucesso.', 'success')
            else:
                flash('Modelo padrão é obrigatório.', 'error')
        
        elif action == 'toggle_model':
            model_id = request.form.get('model_id')
            is_enabled = request.form.get('is_enabled') == 'true'
            
            if model_id:
                try:
                    with app.app_context():
                        model = AIModel.query.filter_by(model_id=model_id).first()
                        if model:
                            model.is_enabled = is_enabled
                            db.session.commit()
                            status_text = "habilitado" if is_enabled else "desabilitado"
                            flash(f'Modelo {model.display_name} {status_text} com sucesso.', 'success')
                        else:
                            flash('Modelo não encontrado.', 'error')
                except Exception as e:
                    flash(f'Erro ao atualizar modelo: {str(e)}', 'error')
            else:
                flash('ID do modelo é obrigatório.', 'error')
        
        elif action == 'add_model':
            provider = request.form.get('provider')
            model_id = request.form.get('model_id')
            display_name = request.form.get('display_name')
            description = request.form.get('description')
            max_tokens = int(request.form.get('max_tokens', 32768))
            context_window = int(request.form.get('context_window', 32768))
            price_input = float(request.form.get('price_input', 0))
            price_output = float(request.form.get('price_output', 0))
            
            if not all([provider, model_id, display_name]):
                flash('Provider, ID do modelo e nome são obrigatórios.', 'error')
            else:
                try:
                    with app.app_context():
                        # Verificar se já existe
                        existing = AIModel.query.filter_by(model_id=model_id).first()
                        if existing:
                            flash('Modelo com este ID já existe.', 'error')
                        else:
                            new_model = AIModel(
                                name=model_id,
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
                            db.session.add(new_model)
                            db.session.commit()
                            flash(f'Modelo {display_name} adicionado com sucesso!', 'success')
                except Exception as e:
                    flash(f'Erro ao adicionar modelo: {str(e)}', 'error')
        
        elif action == 'edit_model':
            original_model_id = request.form.get('original_model_id')
            provider = request.form.get('provider')
            model_id = request.form.get('model_id')
            display_name = request.form.get('display_name')
            description = request.form.get('description')
            max_tokens = int(request.form.get('max_tokens', 32768))
            context_window = int(request.form.get('context_window', 32768))
            price_input = float(request.form.get('price_input', 0))
            price_output = float(request.form.get('price_output', 0))
            
            if not all([original_model_id, provider, model_id, display_name]):
                flash('Provider, ID do modelo e nome são obrigatórios.', 'error')
            else:
                try:
                    with app.app_context():
                        # Buscar o modelo original
                        model = AIModel.query.filter_by(model_id=original_model_id).first()
                        if not model:
                            flash('Modelo não encontrado.', 'error')
                        else:
                            # Verificar se o novo ID já existe (se for diferente do original)
                            if model_id != original_model_id:
                                existing = AIModel.query.filter_by(model_id=model_id).first()
                                if existing:
                                    flash('Já existe um modelo com este ID.', 'error')
                                    return redirect(url_for('admin_config'))
                            
                            # Atualizar os campos
                            model.provider = provider
                            model.model_id = model_id
                            model.name = model_id  # Atualizar também o name
                            model.display_name = display_name
                            model.description = description
                            model.max_tokens = max_tokens
                            model.context_window = context_window
                            model.price_input = price_input
                            model.price_output = price_output
                            model.updated_at = datetime.now(timezone.utc)
                            
                            db.session.commit()
                            flash(f'Modelo {display_name} atualizado com sucesso!', 'success')
                except Exception as e:
                    flash(f'Erro ao atualizar modelo: {str(e)}', 'error')
    
    # Obter configurações atuais
    current_default_model = get_default_ai_model()
    
    # Obter modelos disponíveis com status
    available_models = get_all_models_with_status()
    
    return render_template('admin_config.html', 
                         current_default_model=current_default_model,
                         available_models=available_models)

@app.route('/admin/instructions', methods=['GET', 'POST'])
@login_required
def admin_instructions():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'save_general':
            instructions = request.form.get('general_instructions', '')
            general = GeneralInstructions.query.first()
            if general:
                general.instructions = instructions
                general.updated_at = datetime.now(timezone.utc)
            else:
                general = GeneralInstructions(instructions=instructions)
                db.session.add(general)
            db.session.commit()
            flash('Instruções gerais atualizadas com sucesso!', 'success')
    
    # Obter dados para exibição
    general_instructions = get_general_instructions()
    
    return render_template('admin_instructions.html', 
                         general_instructions=general_instructions)

@app.route('/admin/api_keys', methods=['GET', 'POST'])
@login_required
def admin_api_keys():
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_key':
            provider = request.form.get('provider')
            api_key = request.form.get('api_key')
            
            if not provider or not api_key:
                flash('Todos os campos são obrigatórios.', 'error')
            else:
                set_api_key(provider, api_key)
                flash(f'Chave de API para {provider} configurada com sucesso!', 'success')
        
        elif action == 'test_key':
            provider = request.form.get('provider')
            api_key = request.form.get('api_key')
            
            if not provider or not api_key:
                flash('Todos os campos são obrigatórios.', 'error')
            else:
                try:
                    # Testar a chave
                    if provider == 'openai':
                        import openai
                        openai.api_key = api_key
                        response = openai.models.list()
                        flash(f'Chave OpenAI válida! Modelos disponíveis: {len(response.data)}', 'success')
                    elif provider == 'anthropic':
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        response = client.models.list()
                        flash(f'Chave Anthropic válida! Modelos disponíveis: {len(response.data)}', 'success')
                    elif provider == 'google':
                        from google import genai
                        client = genai.Client(api_key=api_key)
                        models = client.models.list()
                        flash(f'Chave Google válida! Modelos disponíveis: {len(list(models))}', 'success')
                except Exception as e:
                    flash(f'Erro ao testar chave: {str(e)}', 'error')
        
        elif action == 'delete_key':
            provider = request.form.get('provider')
            if provider:
                # Marcar como inativa em vez de deletar
                key = APIKey.query.filter_by(provider=provider).first()
                if key:
                    key.is_active = False
                    db.session.commit()
                    flash(f'Chave de API para {provider} desativada.', 'success')
        
        elif action == 'test_eproc':
            login = request.form.get('eproc_login')
            password = request.form.get('eproc_password')
            
            if not login or not password:
                flash('Login e senha do eproc são obrigatórios.', 'error')
            else:
                success, message = test_eproc_credentials(login, password)
                if success:
                    flash(f'Credenciais do eproc válidas: {message}', 'success')
                else:
                    flash(f'Erro ao testar credenciais do eproc: {message}', 'error')
        
        elif action == 'update_eproc':
            login = request.form.get('eproc_login')
            password = request.form.get('eproc_password')
            
            if not login or not password:
                flash('Login e senha do eproc são obrigatórios.', 'error')
            else:
                set_eproc_credentials(login, password)
                flash('Credenciais do eproc configuradas com sucesso!', 'success')
        
        return redirect(url_for('admin_api_keys'))
    
    # Obter chaves de API e transformar em dicionário
    api_keys_list = get_all_api_keys()
    api_keys = {}
    for key in api_keys_list:
        api_keys[key.provider] = key
    
    # Obter credenciais do eproc
    eproc_credentials = get_eproc_credentials()
    
    return render_template('admin_api_keys.html', api_keys=api_keys, eproc_credentials=eproc_credentials)

@app.route('/admin/debug', methods=['GET'])
@login_required
def admin_debug():
    """Página de debug para visualizar requisições de IA"""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('dashboard'))
    
    # Obter requisições de debug
    debug_requests = get_debug_requests(limit=20)
    
    return render_template('admin_debug.html', debug_requests=debug_requests)

@app.route('/admin/debug/<int:request_id>', methods=['GET'])
@login_required
def admin_debug_detail(request_id):
    """Página de detalhes de uma requisição de debug específica"""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('dashboard'))
    
    # Obter requisição específica
    debug_request = DebugRequest.query.get_or_404(request_id)
    
    return render_template('admin_debug_detail.html', debug_request=debug_request)

@app.route('/api/buscar_movimentos', methods=['POST'])
@login_required
def buscar_movimentos():
    try:
        data = request.get_json()
        numero_processo = data.get('numero_processo')
        sistema = data.get('sistema', 'br.jus.jfrj.eproc')
        
        if not numero_processo:
            return jsonify({'error': 'Número do processo é obrigatório'}), 400
        
        # Limpar número do processo (apenas números)
        numero_processo_limpo = re.sub(r'[^\d]', '', numero_processo)
        
        if len(numero_processo_limpo) < 7:
            return jsonify({'error': 'Número do processo deve ter pelo menos 7 dígitos'}), 400
        
        # Obter credenciais do eproc
        credenciais = get_eproc_credentials()
        if not credenciais:
            return jsonify({'error': 'Credenciais do eproc não configuradas'}), 500
        
        # Autenticar na API
        api = BalcaoJusAPI()
        api.autenticar(credenciais['login'], credenciais['password'])
        
        # Buscar movimentos com número limpo
        resultado = api.buscar_movimentos_processo(numero_processo_limpo, sistema)
        
        # Extrair peças dos movimentos
        movimentos_com_pecas = extrair_pecas_movimentos_balcaojus(resultado)
        
        return jsonify({
            'success': True,
            'movimentos': movimentos_com_pecas,
            'total': len(movimentos_com_pecas)
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar movimentos: {str(e)}")
        return jsonify({'error': f'Erro ao buscar movimentos: {str(e)}'}), 500

@app.route('/api/buscar_conteudo_peca', methods=['POST'])
@login_required
def buscar_conteudo_peca():
    try:
        data = request.get_json()
        numero_processo = data.get('numero_processo')
        id_peca = data.get('id_peca')
        sistema = data.get('sistema', 'br.jus.jfrj.eproc')
        
        if not numero_processo or not id_peca:
            return jsonify({'error': 'Número do processo e ID da peça são obrigatórios'}), 400
        
        # Limpar número do processo (apenas números)
        numero_processo_limpo = re.sub(r'[^\d]', '', numero_processo)
        
        if len(numero_processo_limpo) < 7:
            return jsonify({'error': 'Número do processo deve ter pelo menos 7 dígitos'}), 400
        
        # Obter credenciais do eproc
        credenciais = get_eproc_credentials()
        if not credenciais:
            return jsonify({'error': 'Credenciais do eproc não configuradas'}), 500
        
        # Autenticar na API
        api = BalcaoJusAPI()
        api.autenticar(credenciais['login'], credenciais['password'])
        
        # Obter JWT para download da peça com número limpo
        jwt = api.obter_jwt_peca(numero_processo_limpo, id_peca, sistema)
        
        if not jwt:
            return jsonify({'error': 'Não foi possível obter autorização para download da peça'}), 500
        
        # Fazer download do conteúdo da peça com número limpo
        conteudo_peca = api.download_peca(jwt, numero_processo_limpo, id_peca)
        
        # Detectar formato do conteúdo
        formato = detectar_formato_conteudo(conteudo_peca)
        
        # Extrair texto do conteúdo
        texto_extraido = extrair_texto_conteudo(conteudo_peca, formato)
        
        # Verificar se a extração foi bem-sucedida
        if texto_extraido and not texto_extraido.startswith('Erro ao extrair'):
            response = jsonify({
                'success': True,
                'conteudo_disponivel': True,
                'tamanho_bytes': len(conteudo_peca),
                'formato': formato.upper(),
                'texto_extraido': texto_extraido,
                'mensagem': f'Texto extraído com sucesso do {formato.upper()}.'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        else:
            # Se não conseguiu extrair texto, retornar apenas informações do arquivo
            response = jsonify({
                'success': True,
                'conteudo_disponivel': True,
                'tamanho_bytes': len(conteudo_peca),
                'formato': formato.upper(),
                'texto_extraido': '',
                'mensagem': f'Arquivo {formato.upper()} obtido, mas não foi possível extrair o texto: {texto_extraido}'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar conteúdo da peça: {str(e)}")
        return jsonify({'error': f'Erro ao buscar conteúdo da peça: {str(e)}'}), 500

# Inicialização do banco de dados
def init_db():
    with app.app_context():
        db.create_all()
        
        # Criar usuários padrão se não existirem
        if not User.query.first():
            # Usuários padrão definidos diretamente no código
            default_users = [
                {
                    'email': 'admin@diria.com',
                    'password': 'admin123',
                    'name': 'Administrador',
                    'is_admin': True
                },
                {
                    'email': 'assessor1@diria.com',
                    'password': 'senha123',
                    'name': 'Assessor 1',
                    'is_admin': False
                },
                {
                    'email': 'assessor2@diria.com',
                    'password': 'senha456',
                    'name': 'Assessor 2',
                    'is_admin': False
                }
            ]
            
            for user_data in default_users:
                user = User(
                    email=user_data['email'],
                    name=user_data['name'],
                    is_admin=user_data['is_admin']
                )
                user.set_password(user_data['password'])
                db.session.add(user)
            
            # Criar prompts padrão
            default_prompts = [
                {
                    'name': 'Decisão Padrão',
                    'content': 'Com base nos autos do processo {{numero_processo}}, nas peças processuais apresentadas e nos fundamentos expostos, DECIDO: {{como_decidir}}',
                    'ai_model': 'gemini-2.5-pro',
                    'is_default': True
                },
                {
                    'name': 'Decisão com Fundamentação Detalhada',
                    'content': 'Analisando o processo {{numero_processo}} e as peças processuais: {{pecas_processuais}}, fundamento minha decisão nos seguintes pontos: {{fundamentos}}. Assim, DECIDO: {{como_decidir}}',
                    'ai_model': 'claude-sonnet-4-20250514',
                    'is_default': False
                },
                {
                    'name': 'Decisão com Vedações',
                    'content': 'Considerando as vedações: {{vedacoes}}, e com base no processo {{numero_processo}}, DECIDO: {{como_decidir}}',
                    'ai_model': 'o4-mini-2025-04-16',
                    'is_default': False
                }
            ]
            
            for prompt_data in default_prompts:
                prompt = Prompt(**prompt_data)
                db.session.add(prompt)
            
            # Criar instruções gerais padrão
            if not GeneralInstructions.query.first():
                default_instructions = """Você é um juiz experiente especializado em direito civil, com mais de 20 anos de experiência no Poder Judiciário. 

Suas decisões devem ser baseadas apenas nos fatos apresentados e na legislação aplicável. Use linguagem formal e técnica apropriada para documentos judiciais.

Não mencione nomes de pessoas físicas ou jurídicas específicas. Não faça suposições sobre fatos não apresentados. Base suas decisões apenas nos dados fornecidos e na legislação aplicável."""
                
                general_instructions = GeneralInstructions(instructions=default_instructions)
                db.session.add(general_instructions)
            
            db.session.commit()
            
            # Criar configurações padrão da aplicação
            set_app_config('default_ai_model', 'gemini-2.5-pro', 'Modelo de IA padrão da aplicação')
            
            print("✅ Banco de dados inicializado com sucesso!")
            print("✅ Usuários padrão criados")
            print("✅ Prompts padrão criados")
            print("✅ Instruções gerais criadas")
            print("✅ Configurações padrão criadas")
            print("✅ Tabela de debug criada")
        else:
            # Verificar se a tabela DebugRequest existe, se não, criar
            try:
                DebugRequest.query.first()
                print("✅ Tabela de debug já existe")
            except:
                print("🔄 Criando tabela de debug...")
                db.create_all()
                print("✅ Tabela de debug criada")

if __name__ == '__main__':
    # Configurar argumentos de linha de comando
    parser = argparse.ArgumentParser(description='DIRIA - Sistema de Minutas Judiciais')
    parser.add_argument('--debug', action='store_true', 
                       help='Ativar logs de debug (mostra payloads das APIs)')
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host para executar a aplicação (padrão: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5001, 
                       help='Porta para executar a aplicação (padrão: 5001)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Nível de log (padrão: INFO)')
    
    args = parser.parse_args()
    
    # Configurar logging baseado nos argumentos
    if args.debug:
        # Ativar logs de debug para todas as bibliotecas
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        print("🔍 Modo DEBUG ativado - Logs detalhados das APIs serão exibidos")
    else:
        # Configuração padrão
        logging.basicConfig(
            level=getattr(logging, args.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Inicializar banco de dados
    init_db()
    
    # Executar aplicação
    print(f"🚀 Iniciando DIRIA em http://{args.host}:{args.port}")
    if args.debug:
        print("🔍 Logs de debug ativos - Use Ctrl+C para parar")
    
    app.run(debug=True, host=args.host, port=args.port) 