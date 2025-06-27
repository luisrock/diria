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

class ModelInstructions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(100), unique=True, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
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

class DollarRate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rate = db.Column(db.Float, nullable=False)  # Taxa de câmbio USD/BRL
    date = db.Column(db.Date, nullable=False)   # Data da cotação
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<DollarRate {self.date}: {self.rate}>'

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

def get_model_instructions(model_id):
    """Obtém as instruções específicas de um modelo"""
    instructions = ModelInstructions.query.filter_by(model_id=model_id, is_active=True).first()
    return instructions

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
            raise ValueError("Resposta da API não contém dados válidos")
            
    except Exception as e:
        # Em caso de erro, usar a cotação mais recente disponível
        logger.warning(f"Erro ao buscar cotação do dólar: {e}")
        
        latest_rate = DollarRate.query.order_by(DollarRate.date.desc()).first()
        if latest_rate:
            return latest_rate.rate
        else:
            # Fallback: usar cotação fixa se não houver nenhuma
            return 5.50

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
    prompts = Prompt.query.all()
    default_prompt = Prompt.query.filter_by(is_default=True).first()
    return render_template('dashboard.html', prompts=prompts, default_prompt=default_prompt)

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
        
        # Log de uso detalhado
        log = UsageLog(
            user_id=current_user.id,
            action='generate_minuta',
            tokens_used=tokens_info['total_tokens'],
            request_tokens=tokens_info['request_tokens'],
            response_tokens=tokens_info['response_tokens'],
            model_used=tokens_info['model_used'],
            success=tokens_info['success'],
            error_message=tokens_info.get('error')
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'minuta': minuta,
            'tokens_info': {
                'request_tokens': tokens_info['request_tokens'],
                'response_tokens': tokens_info['response_tokens'],
                'total_tokens': tokens_info['total_tokens'],
                'model_used': tokens_info['model_used'],
                'success': tokens_info['success']
            },
            'cost_info': tokens_info.get('display_info', {}),
            'user_cost': format_cost_for_user(tokens_info.get('cost_info', {}).get('total_cost', 0))
        })
        
    except Exception as e:
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
        
        return jsonify({'error': str(e)}), 500

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
Com base na minuta atual, no histórico de conversa e na solicitação de ajuste, faça as modificações necessárias.

HISTÓRICO DA CONVERSA:
- Prompt original: {prompt.content}
- Dados do processo: {data.get('numero_processo', 'Não informado')}
- Peças processuais: {pecas_texto}
- Como decidir: {data.get('como_decidir', '')}
- Fundamentos: {data.get('fundamentos', '')}
- Vedações: {data.get('vedacoes', '')}

MINUTA ATUAL:
{data.get('current_content', '')}

SOLICITAÇÃO DE AJUSTE:
{data.get('adjustment_prompt', '')}

Por favor, gere uma nova versão da minuta aplicando o ajuste solicitado. Mantenha a estrutura e formatação adequadas para um documento judicial. Considere o contexto completo da conversa para fazer os ajustes apropriados.
"""
        
        # Gerar resposta usando IA com o modelo selecionado
        minuta, tokens_info = ai_manager.generate_response(
            prompt=adjustment_prompt,
            model=ai_model_id,
            max_tokens=2000
        )
        
        # Log de uso detalhado
        log = UsageLog(
            user_id=current_user.id,
            action='adjust_minuta',
            tokens_used=tokens_info['total_tokens'],
            request_tokens=tokens_info['request_tokens'],
            response_tokens=tokens_info['response_tokens'],
            model_used=tokens_info['model_used'],
            success=tokens_info['success'],
            error_message=tokens_info.get('error')
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'minuta': minuta,
            'tokens_info': {
                'request_tokens': tokens_info['request_tokens'],
                'response_tokens': tokens_info['response_tokens'],
                'total_tokens': tokens_info['total_tokens'],
                'model_used': tokens_info['model_used'],
                'success': tokens_info['success']
            },
            'cost_info': tokens_info.get('display_info', {}),
            'user_cost': format_cost_for_user(tokens_info.get('cost_info', {}).get('total_cost', 0))
        })
        
    except Exception as e:
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
        
        return jsonify({'error': str(e)}), 500

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
    
    # Obter modelos atuais do sistema
    available_models = get_all_models()
    
    # Organizar modelos por fabricante
    models_by_provider = {}
    for model_id in available_models:
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
    """Retorna lista de modelos disponíveis"""
    from models_config import get_all_models, get_model_info
    
    models = []
    for model_id in get_all_models():
        info = get_model_info(model_id)
        if info:
            models.append({
                'id': model_id,
                'name': f"{info['display_name']} ({info['provider_name']})",
                'provider': info['provider_name'],
                'description': info['description']
            })
    
    return jsonify({'models': models})

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
    
    # Obter configurações atuais
    current_default_model = get_default_ai_model()
    
    # Obter modelos disponíveis
    from models_config import get_all_models, get_model_info
    available_models = []
    for model_id in get_all_models():
        info = get_model_info(model_id)
        if info:
            available_models.append({
                'id': model_id,
                'name': f"{info['display_name']} ({info['provider_name']})",
                'provider': info['provider_name'],
                'description': info['description']
            })
    
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
        
        if action == 'general':
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
            
        elif action == 'model':
            model_id = request.form.get('model_id')
            instructions = request.form.get('model_instructions', '')
            
            if model_id and instructions:
                existing = ModelInstructions.query.filter_by(model_id=model_id).first()
                if existing:
                    existing.instructions = instructions
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    new_instructions = ModelInstructions(
                        model_id=model_id,
                        instructions=instructions
                    )
                    db.session.add(new_instructions)
                db.session.commit()
                flash(f'Instruções do modelo {model_id} atualizadas com sucesso!', 'success')
    
    # Obter dados para exibição
    general_instructions = get_general_instructions()
    model_instructions = ModelInstructions.query.all()
    available_models = get_all_models()
    
    return render_template('admin_instructions.html', 
                         general_instructions=general_instructions,
                         model_instructions=model_instructions,
                         available_models=available_models)

@app.route('/admin/api_keys', methods=['GET', 'POST'])
@login_required
def admin_api_keys():
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_key':
            provider = request.form.get('provider')
            api_key = request.form.get('api_key', '').strip()
            
            if provider and api_key:
                set_api_key(provider, api_key)
                flash(f'Chave da API {provider} atualizada com sucesso!', 'success')
            elif provider and not api_key:
                # Desativar chave
                existing = APIKey.query.filter_by(provider=provider).first()
                if existing:
                    existing.is_active = False
                    existing.updated_at = datetime.now(timezone.utc)
                    db.session.commit()
                    flash(f'Chave da API {provider} desativada!', 'success')
        
        elif action == 'test_key':
            provider = request.form.get('provider')
            api_key = get_api_key(provider)
            
            if api_key:
                # Testar a chave (implementação básica)
                try:
                    if provider == 'openai':
                        import openai
                        client = openai.OpenAI(api_key=api_key)
                        response = client.models.list()
                        flash(f'Chave da API {provider} válida!', 'success')
                    elif provider == 'anthropic':
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        # Teste básico
                        flash(f'Chave da API {provider} válida!', 'success')
                    elif provider == 'google':
                        import google.generativeai as genai
                        genai.configure(api_key=api_key)
                        # Teste básico
                        flash(f'Chave da API {provider} válida!', 'success')
                except Exception as e:
                    flash(f'Erro ao testar chave da API {provider}: {str(e)}', 'error')
            else:
                flash(f'Chave da API {provider} não encontrada!', 'error')
    
    # Obter chaves existentes
    api_keys = get_all_api_keys()
    
    # Criar dicionário para facilitar o acesso
    keys_dict = {key.provider: key for key in api_keys}
    
    return render_template('admin_api_keys.html', api_keys=keys_dict)

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