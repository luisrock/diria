# 🏛️ DIRIA - Sistema de Minutas Judiciais

Sistema inteligente para geração de minutas de decisão judicial utilizando múltiplas APIs de Inteligência Artificial.

## 🚀 Funcionalidades

### ✨ Principais
- **Geração de Minutas**: Interface intuitiva para criar minutas de decisão judicial
- **Múltiplas IAs**: Suporte a OpenAI (GPT), Anthropic (Claude) e Google (Gemini)
- **Editor Rico**: CKEditor integrado para edição e formatação de minutas
- **Sistema de Usuários**: Controle de acesso com roles de administrador e usuário
- **Gestão de Prompts**: Templates personalizáveis para diferentes tipos de decisão

### 🛠️ Administrativas
- **Painel Admin**: Interface completa para gestão do sistema
- **Logs Detalhados**: Monitoramento de uso e tokens por usuário/modelo
- **Estatísticas**: Métricas de performance e utilização
- **Gestão de Usuários**: CRUD completo de usuários do sistema

### 📝 Editor Avançado
- **Formatação Rica**: Negrito, itálico, listas, títulos, etc.
- **Cópia com Formatação**: Preserva formatação HTML para colagem em outros editores
- **Download**: Exportação de minutas como arquivo HTML
- **Backup Automático**: Salvamento automático no navegador
- **Indicador de Edição**: Mostra quando o conteúdo foi modificado

## 🛠️ Tecnologias

- **Backend**: Flask, SQLAlchemy, Flask-Login
- **Frontend**: HTML5, CSS3 (Tailwind), JavaScript
- **Editor**: CKEditor 5
- **Banco de Dados**: SQLite (configurável)
- **APIs de IA**: OpenAI, Anthropic, Google Generative AI

## 📋 Pré-requisitos

- Python 3.8+
- pip
- Chaves de API das IAs (opcional para teste)

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/luisrock/diria.git
cd diria
```

### 2. Crie um ambiente virtual
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente
```bash
cp env_example.txt .env
```

Edite o arquivo `.env` e adicione suas chaves de API:
```env
# Configurações do Flask
SECRET_KEY=sua_chave_secreta_aqui
FLASK_ENV=development

# Configurações de Banco de Dados
DATABASE_URL=sqlite:///diria.db

# Chaves de API dos modelos de IA (opcional)
OPENAI_API_KEY=sua_chave_openai_aqui
ANTHROPIC_API_KEY=sua_chave_anthropic_aqui
GOOGLE_API_KEY=sua_chave_google_aqui
```

### 5. Inicialize o banco de dados
```bash
python -c "from app import init_db; init_db()"
```

### 6. Execute a aplicação
```bash
python app.py
```

A aplicação estará disponível em: http://localhost:5001

## 👥 Usuários Padrão

O sistema cria automaticamente os seguintes usuários:

| Email | Senha | Tipo |
|-------|-------|------|
| admin@diria.com | admin123 | Administrador |
| assessor1@diria.com | senha123 | Usuário |
| assessor2@diria.com | senha456 | Usuário |

## 🎯 Como Usar

### 1. Login
- Acesse http://localhost:5001
- Faça login com um dos usuários padrão
- Altere a senha no primeiro acesso

### 2. Gerar Minuta
- Preencha o número do processo (opcional)
- Adicione as peças processuais
- Descreva como decidir
- Adicione fundamentos e vedações (opcional)
- Selecione o modelo de prompt
- Clique em "Gerar Minuta"

### 3. Editar e Exportar
- Use o CKEditor para fazer ajustes
- Copie com formatação preservada
- Baixe como arquivo HTML
- Use o sistema de backup automático

## 🔧 Scripts Úteis

### Verificar Usuários
```bash
python check_users.py
```

### Testar Chaves de API
```bash
python test_api_keys.py
```

### Migrar Banco de Dados
```bash
python migrate_db.py
```

### Gerenciar Modelos de IA
```bash
python manage_models.py
```

## 📊 Modelos de IA Suportados

### OpenAI
- **O3**: Modelo mais poderoso, mas lento
- **O4 Mini**: Mais rápido e econômico

### Anthropic
- **Claude Sonnet 4**: Alto desempenho
- **Claude Sonnet 3.7**: Com pensamento estendido

### Google
- **Gemini 2.5 Pro**: Estado da arte
- **Gemini 2.5 Flash**: Melhor custo-benefício

## 🏗️ Estrutura do Projeto

```
diria/
├── app.py                 # Aplicação principal
├── ai_manager.py          # Gerenciador de APIs de IA
├── models_config.py       # Configuração dos modelos
├── requirements.txt       # Dependências Python
├── .env                   # Variáveis de ambiente
├── .gitignore            # Arquivos ignorados pelo Git
├── README.md             # Documentação
├── templates/            # Templates HTML
│   ├── base.html         # Template base
│   ├── dashboard.html    # Dashboard principal
│   ├── login.html        # Página de login
│   └── admin_*.html      # Páginas administrativas
├── static/               # Arquivos estáticos
├── instance/             # Banco de dados SQLite
└── scripts/              # Scripts utilitários
```

## 🔒 Segurança

- Senhas hasheadas com Werkzeug
- Controle de acesso por roles
- Validação de entrada
- Logs de auditoria
- Proteção contra CSRF

## 📈 Monitoramento

- Contagem detalhada de tokens
- Estatísticas por usuário/modelo
- Logs de sucesso/erro
- Métricas de performance

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🆘 Suporte

Para suporte, abra uma issue no GitHub ou entre em contato através do email do projeto.

## 🔄 Changelog

### v1.0.0
- ✅ Sistema base completo
- ✅ Integração com múltiplas IAs
- ✅ Editor CKEditor integrado
- ✅ Sistema de usuários e admin
- ✅ Backup automático
- ✅ Cópia com formatação preservada

---

**Desenvolvido com ❤️ para facilitar a criação de minutas judiciais** 