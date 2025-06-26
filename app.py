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
    persona = db.Column(db.Text, nullable=True)
    restrictions = db.Column(db.Text, nullable=True)
    introduction = db.Column(db.Text, nullable=True)
    conclusion = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

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

def format_instructions_for_provider(instructions, provider, model_id):
    """Formata as instruções de acordo com o provedor da API"""
    if not instructions:
        return ""
    
    formatted_prompt = ""
    
    if provider == "openai":
        # OpenAI: Usar system message para persona e restrições
        system_message = ""
        if instructions.persona:
            system_message += f"Você é: {instructions.persona}\n\n"
        if instructions.restrictions:
            system_message += f"Restrições: {instructions.restrictions}\n\n"
        
        # Se há system message, retornar como dicionário para ser usado como system message
        if system_message:
            return {
                "system_message": system_message.strip(),
                "user_prefix": instructions.introduction if instructions.introduction else ""
            }
        else:
            # Fallback para formato antigo se não há persona/restrições
            if instructions.introduction:
                formatted_prompt += f"Introdução: {instructions.introduction}\n\n"
    
    elif provider == "anthropic":
        # Anthropic: Usar system message para persona e restrições
        system_message = ""
        if instructions.persona:
            system_message += f"Você é: {instructions.persona}\n\n"
        if instructions.restrictions:
            system_message += f"Restrições: {instructions.restrictions}\n\n"
        
        # Se há system message, retornar como dicionário para ser usado como system message
        if system_message:
            return {
                "system_message": system_message.strip(),
                "user_prefix": instructions.introduction if instructions.introduction else ""
            }
        else:
            # Fallback para formato antigo se não há persona/restrições
            if instructions.introduction:
                formatted_prompt += f"Introdução: {instructions.introduction}\n\n"
    
    elif provider == "google":
        # Google: Usar system_instruction (nova funcionalidade)
        system_message = ""
        if instructions.persona:
            system_message += f"Você é: {instructions.persona}\n\n"
        if instructions.restrictions:
            system_message += f"Restrições: {instructions.restrictions}\n\n"
        
        # Se há system message, retornar como dicionário para ser usado como system_instruction
        if system_message:
            return {
                "system_message": system_message.strip(),
                "user_prefix": instructions.introduction if instructions.introduction else ""
            }
        else:
            # Fallback para formato antigo se não há persona/restrições
            if instructions.introduction:
                formatted_prompt += f"Introdução: {instructions.introduction}\n\n"
    
    return formatted_prompt

def format_conclusion_for_provider(instructions, provider):
    """Formata a conclusão de acordo com o provedor da API"""
    if not instructions or not instructions.conclusion:
        return ""
    
    return f"\n\n{instructions.conclusion}"

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
            }
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
            }
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
    return render_template('admin_logs.html', logs=logs)

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
    
    # Tokens por modelo
    tokens_by_model = db.session.query(
        UsageLog.model_used,
        db.func.sum(UsageLog.tokens_used).label('total_tokens'),
        db.func.count(UsageLog.id).label('count')
    ).filter(
        UsageLog.model_used.isnot(None),
        UsageLog.tokens_used > 0
    ).group_by(UsageLog.model_used).all()
    
    # Tokens por usuário
    tokens_by_user = db.session.query(
        User.name,
        db.func.sum(UsageLog.tokens_used).label('total_tokens'),
        db.func.count(UsageLog.id).label('count')
    ).join(UsageLog).filter(
        UsageLog.tokens_used > 0
    ).group_by(User.id, User.name).all()
    
    # Últimos 7 dias
    from datetime import timedelta
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
    
    stats = {
        'total_logs': total_logs,
        'total_tokens': total_tokens,
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0,
        'tokens_by_model': tokens_by_model,
        'tokens_by_user': tokens_by_user,
        'recent_logs': recent_logs,
        'recent_tokens': recent_tokens
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
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            model_id = request.form.get('model_id')
            persona = request.form.get('persona')
            restrictions = request.form.get('restrictions')
            introduction = request.form.get('introduction')
            conclusion = request.form.get('conclusion')
            is_active = request.form.get('is_active') == 'on'
            
            # Verificar se já existe instrução para este modelo
            existing = ModelInstructions.query.filter_by(model_id=model_id).first()
            if existing:
                flash(f'Já existem instruções configuradas para o modelo {model_id}. Use a opção de edição.', 'error')
            else:
                instruction = ModelInstructions(
                    model_id=model_id,
                    persona=persona,
                    restrictions=restrictions,
                    introduction=introduction,
                    conclusion=conclusion,
                    is_active=is_active
                )
                db.session.add(instruction)
                db.session.commit()
                flash(f'Instruções criadas com sucesso para o modelo {model_id}.', 'success')
        
        elif action == 'update':
            model_id = request.form.get('model_id')
            persona = request.form.get('persona')
            restrictions = request.form.get('restrictions')
            introduction = request.form.get('introduction')
            conclusion = request.form.get('conclusion')
            is_active = request.form.get('is_active') == 'on'
            
            instruction = ModelInstructions.query.filter_by(model_id=model_id).first()
            if instruction:
                instruction.persona = persona
                instruction.restrictions = restrictions
                instruction.introduction = introduction
                instruction.conclusion = conclusion
                instruction.is_active = is_active
                instruction.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                flash(f'Instruções atualizadas com sucesso para o modelo {model_id}.', 'success')
            else:
                flash(f'Instruções não encontradas para o modelo {model_id}.', 'error')
        
        elif action == 'delete':
            model_id = request.form.get('model_id')
            instruction = ModelInstructions.query.filter_by(model_id=model_id).first()
            if instruction:
                db.session.delete(instruction)
                db.session.commit()
                flash(f'Instruções excluídas com sucesso para o modelo {model_id}.', 'success')
            else:
                flash(f'Instruções não encontradas para o modelo {model_id}.', 'error')
        
        elif action == 'apply_to_all':
            # Aplicar instruções a todos os modelos disponíveis
            persona = request.form.get('persona')
            restrictions = request.form.get('restrictions')
            introduction = request.form.get('introduction')
            conclusion = request.form.get('conclusion')
            is_active = request.form.get('is_active') == 'on'
            
            # Obter todos os modelos disponíveis
            from models_config import get_all_models
            all_model_ids = get_all_models()
            
            success_count = 0
            error_count = 0
            
            for model_id in all_model_ids:
                try:
                    # Verificar se já existe instrução para este modelo
                    existing = ModelInstructions.query.filter_by(model_id=model_id).first()
                    
                    if existing:
                        # Atualizar instrução existente
                        existing.persona = persona
                        existing.restrictions = restrictions
                        existing.introduction = introduction
                        existing.conclusion = conclusion
                        existing.is_active = is_active
                        existing.updated_at = datetime.now(timezone.utc)
                    else:
                        # Criar nova instrução
                        instruction = ModelInstructions(
                            model_id=model_id,
                            persona=persona,
                            restrictions=restrictions,
                            introduction=introduction,
                            conclusion=conclusion,
                            is_active=is_active
                        )
                        db.session.add(instruction)
                    
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    logger.error(f"Erro ao aplicar instruções para modelo {model_id}: {e}")
            
            db.session.commit()
            
            if request.headers.get('Accept') == 'application/json':
                return jsonify({
                    'success': True,
                    'message': f'Instruções aplicadas com sucesso a {success_count} modelos.',
                    'success_count': success_count,
                    'error_count': error_count
                })
            else:
                if error_count == 0:
                    flash(f'Instruções aplicadas com sucesso a {success_count} modelos.', 'success')
                else:
                    flash(f'Instruções aplicadas a {success_count} modelos. {error_count} erros ocorreram.', 'warning')
    
    # Obter dados para o template
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
    instructions_list = ModelInstructions.query.order_by(ModelInstructions.model_id).all()
    
    return render_template('admin_instructions.html', 
                         available_models=available_models,
                         instructions_list=instructions_list)

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
            
            db.session.commit()
            
            # Criar configurações padrão da aplicação
            set_app_config('default_ai_model', 'gemini-2.5-pro', 'Modelo de IA padrão da aplicação')
            
            print("✅ Banco de dados inicializado com sucesso!")
            print("✅ Usuários padrão criados")
            print("✅ Prompts padrão criados")
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