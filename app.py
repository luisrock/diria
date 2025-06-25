from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.urls import url_parse
from datetime import datetime
import os
from dotenv import load_dotenv
import re
import json
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('logs', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
        
        # Gerar resposta usando IA
        minuta, tokens_info = ai_manager.generate_response(
            prompt=prompt_content,
            model=prompt.ai_model,
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
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5001) 