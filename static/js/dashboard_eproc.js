// Dashboard Eproc - JavaScript
// Funcionalidades para integração com sistema eproc

// Variáveis globais
let movimentosData = [];
let movimentosSelecionados = new Set();
let paginaAtual = 1;
let itensPorPagina = 10;
let processoAtual = '';
let modalPovoado = false;
let movimentosCache = {};
let pecasImportadas = [];
let pecasManuais = [];
let editor = null;
let dragSource = null;
let dragTarget = null;
let currentFormData = null; // Dados do formulário original
let ordemInvertida = false; // Nova variável para controlar a ordem
let objetivoAtual = 'minuta'; // Objetivo selecionado atualmente


// Função para selecionar objetivo
function selecionarObjetivo(objetivo) {
    objetivoAtual = objetivo;
    
    // Atualizar botões
    const botoes = document.querySelectorAll('.objetivo-btn');
    botoes.forEach(btn => {
        btn.classList.remove('bg-primary-600', 'text-white', 'hover:bg-primary-700', 'focus:ring-primary-500');
        btn.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300', 'focus:ring-gray-500');
    });
    
    // Ativar botão selecionado
    const botaoSelecionado = document.getElementById(`btn-${objetivo}`);
    if (botaoSelecionado) {
        botaoSelecionado.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300', 'focus:ring-gray-500');
        botaoSelecionado.classList.add('bg-primary-600', 'text-white', 'hover:bg-primary-700', 'focus:ring-primary-500');
    }
    
    // Atualizar campo hidden
    document.getElementById('objetivo_selecionado').value = objetivo;
    
    // Atualizar textos dinamicamente
    atualizarTextosDinamicos(objetivo);
    
    // Mostrar/ocultar campos específicos
    const camposMinuta = document.getElementById('campos-minuta');
    const camposOutros = document.getElementById('campos-outros');
    
    if (objetivo === 'minuta') {
        camposMinuta.classList.remove('hidden');
        camposOutros.classList.add('hidden');
        
        // Tornar campos obrigatórios
        document.getElementById('como_decidir').required = true;
        document.getElementById('instrucoes_adicionais').required = false;
    } else {
        camposMinuta.classList.add('hidden');
        camposOutros.classList.remove('hidden');
        
        // Tornar campos obrigatórios
        document.getElementById('como_decidir').required = false;
        document.getElementById('instrucoes_adicionais').required = false;
    }
    
    // Carregar prompts do objetivo selecionado
    // Aguardar um pouco para garantir que os modelos foram carregados
    setTimeout(() => {
        carregarPromptsPorObjetivo(objetivo);
    }, 100);
}

// Função para atualizar textos dinamicamente baseado no objetivo
function atualizarTextosDinamicos(objetivo) {
    const btnGerarTexto = document.getElementById('btn-gerar-texto');
    const resultadoTitulo = document.getElementById('resultado-titulo');
    
    const textos = {
        'minuta': {
            btn: 'Gerar Minuta',
            titulo: 'Minuta Gerada'
        },
        'resumo': {
            btn: 'Gerar Resumo',
            titulo: 'Resumo Gerado'
        },
        'relatorio': {
            btn: 'Gerar Relatório',
            titulo: 'Relatório Gerado'
        }
    };
    
    const texto = textos[objetivo] || textos['minuta'];
    
    if (btnGerarTexto) {
        btnGerarTexto.textContent = texto.btn;
    }
    
    if (resultadoTitulo) {
        resultadoTitulo.textContent = texto.titulo;
    }
}

// Função para carregar prompts por objetivo
async function carregarPromptsPorObjetivo(objetivo) {
    try {
        const response = await fetch(`/api/prompts/${objetivo}`);
        const data = await response.json();
        
        if (data.prompts) {
            const promptSelect = document.getElementById('prompt_select');
            promptSelect.innerHTML = '';
            
            let defaultPrompt = null;
            
            data.prompts.forEach(prompt => {
                const option = document.createElement('option');
                option.value = prompt.id;
                option.textContent = prompt.name;
                option.dataset.aiModel = prompt.ai_model; // Armazenar o modelo do prompt
                if (prompt.is_default) {
                    option.selected = true;
                    defaultPrompt = prompt;
                }
                promptSelect.appendChild(option);
            });
            
            // Carregar o modelo padrão do prompt padrão
            if (defaultPrompt && defaultPrompt.ai_model) {
                carregarModeloDoPrompt(defaultPrompt.ai_model);
            } else {
                // Se não encontrar modelo do prompt padrão, usar o padrão da aplicação
                loadDefaultModel();
            }
        }
    } catch (error) {
        console.error('Erro ao carregar prompts:', error);
        // Em caso de erro, carregar modelo padrão da aplicação
        loadDefaultModel();
    }
}

// Função para carregar o modelo de um prompt específico
function carregarModeloDoPrompt(aiModel) {
    const modelSelect = document.getElementById('ai_model_select');
    if (modelSelect && aiModel) {
        // Procurar a opção com o modelo do prompt
        const option = modelSelect.querySelector(`option[value="${aiModel}"]`);
        if (option) {
            option.selected = true;
        } else {
            // Se não encontrar, usar o modelo padrão da aplicação
            loadDefaultModel();
        }
    } else {
        // Se não há modelo especificado, usar o padrão da aplicação
        loadDefaultModel();
    }
}

// Função para limpar número do processo (apenas números)
function limparNumeroProcesso(input) {
    const valor = input.value;
    const numeros = valor.replace(/\D/g, '');
    
    if (numeros.length > 0) {
        // Formatar como processo judicial
        let formatado = '';
        for (let i = 0; i < numeros.length && i < 20; i++) {
            if (i === 7 || i === 9 || i === 11 || i === 13 || i === 15) {
                formatado += '.';
            }
            if (i === 17) {
                formatado += '-';
            }
            formatado += numeros[i];
        }
        input.value = formatado;
    }
    
    // Habilitar/desabilitar botão baseado no comprimento
    const btnResgatar = document.getElementById('btnResgatarMovimentos');
    if (btnResgatar) {
        btnResgatar.disabled = numeros.length < 7;
    }
}

// Função para ordenar peças por evento
function ordenarPecasPorEvento() {
    const container = document.getElementById('pecas-container');
    const pecasItems = container.querySelectorAll('.peca-item');
    const pecasArray = Array.from(pecasItems);
    
    // Ordenar por evento (assumindo que o evento está no nome da peça)
    pecasArray.sort((a, b) => {
        const nomeA = a.querySelector('input[name="peca_nome[]"]').value;
        const nomeB = b.querySelector('input[name="peca_nome[]"]').value;
        return nomeA.localeCompare(nomeB);
    });
    
    // Reordenar no DOM
    pecasArray.forEach(peca => container.appendChild(peca));
}

// Função para adicionar nova peça
function addPeca() {
    const container = document.getElementById('pecas-container');
    const newPeca = document.createElement('div');
    newPeca.className = 'peca-item bg-gray-50 border border-gray-200 rounded-lg p-4';
    newPeca.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nome da Peça</label>
                <input type="text" name="peca_nome[]" required
                       class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                       placeholder="Ex: Petição Inicial">
            </div>
            <div class="flex items-end">
                <button type="button" onclick="removePeca(this)" 
                        class="text-red-600 hover:text-red-800">
                    <i class="fas fa-trash"></i> Remover
                </button>
            </div>
        </div>
        <div class="mt-3">
            <label class="block text-sm font-medium text-gray-700 mb-1">Conteúdo da Peça</label>
            <textarea name="peca_conteudo[]" rows="4" required
                      class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                      placeholder="Cole o conteúdo da peça processual..."></textarea>
        </div>
    `;
    container.appendChild(newPeca);
}

// Função para remover peça
function removePeca(button) {
    const pecaItem = button.closest('.peca-item');
    const container = document.getElementById('pecas-container');
    const pecasItems = container.querySelectorAll('.peca-item');
    
    if (pecasItems.length > 1) {
        pecaItem.remove();
    } else {
        // Limpar campos se for a última peça
        const inputs = pecaItem.querySelectorAll('input, textarea');
        inputs.forEach(input => input.value = '');
    }
}

// Função para abrir modal de movimentos
function abrirModalMovimentos() {
    const numeroProcesso = document.getElementById('numero_processo').value.trim();
    if (!numeroProcesso) {
        alert('Digite um número de processo válido.');
        return;
    }
    
    // Limpar dados anteriores se modal não foi povoado
    if (!modalPovoado) {
        movimentosData = [];
        movimentosSelecionados.clear();
        paginaAtual = 1;
        ordemInvertida = false; // Resetar estado da ordem
    }
    
    // Atualizar número do processo no modal
    document.getElementById('numeroProcessoModal').textContent = numeroProcesso;
    
    // Botão de inverter ordem mantém aparência fixa
    
    // Mostrar modal
    document.getElementById('modalMovimentos').style.display = 'block';
    
    // Buscar movimentos se modal não foi povoado
    if (!modalPovoado) {
        buscarMovimentos();
    } else {
        // Sincronizar seleções com peças existentes
        sincronizarSelecoesModal();
    }
}

// Função para fechar modal de movimentos
function fecharModalMovimentos() {
    document.getElementById('modalMovimentos').style.display = 'none';
    
    // Limpar informação sobre peças já importadas
    const infoDiv = document.querySelector('.bg-blue-50');
    if (infoDiv) {
        infoDiv.remove();
    }
    
    // Reabilitar todos os checkboxes
    const checkboxes = document.querySelectorAll('.peca-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.disabled = false;
        checkbox.parentElement.style.opacity = '1';
    });
}

// Função para buscar movimentos via API
function buscarMovimentos() {
    const numeroProcesso = document.getElementById('numero_processo').value.trim();
    
    // Mostrar loading
    document.getElementById('loadingMovimentos').classList.remove('hidden');
    document.getElementById('conteudoMovimentos').classList.add('hidden');
    document.getElementById('erroMovimentos').classList.add('hidden');
    
    // Fazer requisição para a API
    fetch('/api/buscar_movimentos', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            numero_processo: numeroProcesso,
            sistema: 'br.jus.jfrj.eproc'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            exibirMovimentos(data.movimentos);
        } else {
            throw new Error(data.error || 'Erro desconhecido');
        }
    })
    .catch(error => {
        console.error('Erro ao buscar movimentos:', error);
        document.getElementById('loadingMovimentos').classList.add('hidden');
        document.getElementById('conteudoMovimentos').classList.add('hidden');
        document.getElementById('erroMovimentos').classList.remove('hidden');
        document.getElementById('mensagemErro').textContent = error.message;
    });
}

function exibirMovimentos(movimentos) {
    const loadingDiv = document.getElementById('loadingMovimentos');
    const conteudoDiv = document.getElementById('conteudoMovimentos');
    const erroDiv = document.getElementById('erroMovimentos');

    if (!movimentos || movimentos.length === 0) {
        loadingDiv.classList.add('hidden');
        conteudoDiv.classList.add('hidden');
        erroDiv.classList.remove('hidden');
        document.getElementById('mensagemErro').textContent = 'Nenhum movimento com peças encontrado para este processo.';
        return;
    }

    loadingDiv.classList.add('hidden');
    erroDiv.classList.add('hidden');
    conteudoDiv.classList.remove('hidden');

    // Converter dados da API para o formato esperado pelo código existente
    movimentosData = movimentos.map(mov => ({
        id: mov.evento,
        evento: mov.evento,
        data: mov.data,
        descricao: mov.descricao,
        temPeca: true,
        pecas: mov.pecas.map(peca => ({
            id: String(peca.id), // Garantir que ID seja string
            descricao: peca.descricao,
            tipo: peca.tipo,
            mimetype: peca.mimetype,
            rotulo: peca.rotulo,
            tamanho: peca.tamanho,
            data: peca.data
        }))
    }));

    // Inverter a ordem inicial para mostrar eventos mais recentes primeiro
    movimentosData.reverse();
    
    // Inverter também a ordem das peças dentro de cada movimento
    movimentosData.forEach(movimento => {
        if (movimento.pecas && movimento.pecas.length > 0) {
            movimento.pecas.reverse();
        }
    });
    
    // Definir estado inicial como invertido
    ordemInvertida = true;

    // Renderizar primeira página
    paginaAtual = 1;
    renderizarMovimentos();

    // Marcar modal como povoado
    modalPovoado = true;
}

function renderizarMovimentos() {
    const tbody = document.getElementById('tabelaMovimentos');
    const inicio = (paginaAtual - 1) * itensPorPagina;
    const fim = inicio + itensPorPagina;
    const movimentosPagina = movimentosData.slice(inicio, fim);
    
    tbody.innerHTML = '';
    
    movimentosPagina.forEach(movimento => {
        // Para cada movimento, criar uma linha para cada peça
        if (movimento.pecas && movimento.pecas.length > 0) {
            movimento.pecas.forEach((peca, pecaIndex) => {
                const tr = document.createElement('tr');
                
                tr.innerHTML = `
                    <td class="text-center">
                        <input type="checkbox" class="peca-checkbox" 
                               value="${peca.id}" 
                               data-evento="${movimento.evento}"
                               onchange="togglePeca('${peca.id}')"
                               ${movimentosSelecionados.has(peca.id) ? 'checked' : ''}>
                    </td>
                    <td>${movimento.evento}</td>
                    <td>${movimento.data}</td>
                    <td>${movimento.descricao}</td>
                    <td class="text-center" style="width: 100px;">
                        <button type="button" class="btn btn-sm btn-primary btn-visualizar-peca" 
                                data-id="${peca.id}" data-rotulo="${peca.rotulo || peca.descricao}" 
                                style="background-color: #3b82f6; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 12px; cursor: pointer;">
                            ${peca.rotulo || peca.descricao}
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            // Movimento sem peças - mostrar apenas uma linha sem checkbox
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="text-center">
                    <span class="text-gray-400">-</span>
                </td>
                <td>${movimento.evento}</td>
                <td>${movimento.data}</td>
                <td>${movimento.descricao}</td>
                <td class="text-center" style="width: 100px;">
                    <span class="text-gray-400">Sem peças</span>
                </td>
            `;
            tbody.appendChild(tr);
        }
    });
    
    // Atualizar informações de paginação
    atualizarPaginacao();
    
    // Atualizar checkbox "selecionar todas" após renderizar
    setTimeout(() => {
        const selectAll = document.getElementById('selectAll');
        const checkboxes = document.querySelectorAll('.peca-checkbox');
        if (selectAll && checkboxes.length > 0) {
            const totalCheckboxes = checkboxes.length;
            const checkedCheckboxes = Array.from(checkboxes).filter(cb => cb.checked).length;
            selectAll.checked = checkedCheckboxes === totalCheckboxes;
            selectAll.indeterminate = checkedCheckboxes > 0 && checkedCheckboxes < totalCheckboxes;
        }
        
        // Adicionar eventos de clique para os botões de visualizar peça
        document.querySelectorAll('.btn-visualizar-peca').forEach(btn => {
            btn.addEventListener('click', function() {
                const pecaId = this.getAttribute('data-id');
                const rotulo = this.getAttribute('data-rotulo');
                visualizarPeca(pecaId, rotulo);
            });
        });
        
        // Adicionar event listener para o checkbox "selecionar todas"
        const selectAllCheckbox = document.getElementById('selectAll');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const checkboxes = document.querySelectorAll('.peca-checkbox');
                checkboxes.forEach(checkbox => {
                    if (this.checked) {
                        checkbox.checked = true;
                        movimentosSelecionados.add(checkbox.value);
                    } else {
                        checkbox.checked = false;
                        movimentosSelecionados.delete(checkbox.value);
                    }
                });
                atualizarContadorSelecionados();
            });
        }
    }, 0);
}

function atualizarPaginacao() {
    const total = movimentosData.length;
    const inicio = (paginaAtual - 1) * itensPorPagina + 1;
    const fim = Math.min(paginaAtual * itensPorPagina, total);
    
    document.getElementById('infoPaginacao').textContent = 
        `Mostrando ${inicio}-${fim} de ${total} movimentos`;
}

function paginaAnterior() {
    if (paginaAtual > 1) {
        paginaAtual--;
        renderizarMovimentos();
    }
}

function paginaProxima() {
    const totalPaginas = Math.ceil(movimentosData.length / itensPorPagina);
    if (paginaAtual < totalPaginas) {
        paginaAtual++;
        renderizarMovimentos();
    }
}

// Função para alternar seleção de uma peça específica
function togglePeca(pecaId) {
    if (movimentosSelecionados.has(pecaId)) {
        movimentosSelecionados.delete(pecaId);
    } else {
        movimentosSelecionados.add(pecaId);
    }
    
    atualizarContadorSelecionados();
}

// Função para selecionar/desselecionar todas as peças (removida - agora usa event listener)

// Função para formatar data (YYYYMMDDHHMMSS -> DD/MM/YYYY HH:MM)
function formatarData(dataString) {
    if (!dataString || dataString.length < 8) {
        return dataString;
    }
    
    try {
        const ano = dataString.substring(0, 4);
        const mes = dataString.substring(4, 6);
        const dia = dataString.substring(6, 8);
        const hora = dataString.length >= 10 ? dataString.substring(8, 10) : '00';
        const minuto = dataString.length >= 12 ? dataString.substring(10, 12) : '00';
        
        return `${dia}/${mes}/${ano} ${hora}:${minuto}`;
    } catch (error) {
        return dataString;
    }
}

// Função para atualizar o contador de itens selecionados
function atualizarContadorSelecionados() {
    // Atualizar contador no cabeçalho do modal
    const contador = document.getElementById('contadorSelecionados');
    if (contador) {
        contador.textContent = movimentosSelecionados.size;
    }
    
    // Atualizar contador no botão de importar
    const contadorBotao = document.getElementById('contadorSelecionadosBotao');
    if (contadorBotao) {
        contadorBotao.textContent = movimentosSelecionados.size;
    }
    
    // Atualizar estado do checkbox "selecionar todas"
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.peca-checkbox');
    if (selectAll && checkboxes.length > 0) {
        const totalCheckboxes = checkboxes.length;
        const checkedCheckboxes = Array.from(checkboxes).filter(cb => cb.checked).length;
        selectAll.checked = checkedCheckboxes === totalCheckboxes;
        selectAll.indeterminate = checkedCheckboxes > 0 && checkedCheckboxes < totalCheckboxes;
    }
}

// Função para importar peças selecionadas
async function importarPecas() {
    if (movimentosSelecionados.size === 0) {
        alert('Selecione pelo menos uma peça para importar.');
        return;
    }
    
    // Obter número do processo
    const numeroProcesso = document.getElementById('numero_processo').value.trim();
    if (!numeroProcesso) {
        alert('Número do processo é obrigatório para importar peças.');
        return;
    }
    
    // Verificar peças já importadas
    const container = document.getElementById('pecas-container');
    const pecasJaImportadas = new Set();
    const pecasExistentes = container.querySelectorAll('.peca-item');
    
    pecasExistentes.forEach(pecaItem => {
        const pecaId = pecaItem.dataset.pecaId;
        if (pecaId) {
            pecasJaImportadas.add(pecaId);
        }
    });
    
    // Filtrar apenas peças que ainda não foram importadas
    const pecasParaImportar = [];
    
    movimentosData.forEach(movimento => {
        if (movimento.pecas) {
            movimento.pecas.forEach(peca => {
                if (movimentosSelecionados.has(peca.id) && !pecasJaImportadas.has(peca.id)) {
                    pecasParaImportar.push({
                        id: peca.id,
                        rotulo: peca.rotulo || peca.descricao,
                        descricao: peca.descricao,
                        evento: movimento.evento,
                        data: movimento.data,
                        movimentoDescricao: movimento.descricao
                    });
                }
            });
        }
    });
    
    if (pecasParaImportar.length === 0) {
        alert('Todas as peças selecionadas já foram importadas.');
        return;
    }
    
    // Mostrar loading no modal
    const modalBody = document.querySelector('.modal-body');
    const conteudoMovimentos = document.getElementById('conteudoMovimentos');
    const loadingImportacao = document.createElement('div');
    loadingImportacao.id = 'loadingImportacao';
    loadingImportacao.className = 'text-center py-8';
    loadingImportacao.innerHTML = `
        <div class="loading-spinner mx-auto mb-4"></div>
        <p class="text-lg font-medium text-gray-900">Importando peças...</p>
        <p class="text-sm text-gray-600">Buscando conteúdo de ${pecasParaImportar.length} peça(s) selecionada(s)</p>
        <p class="text-xs text-gray-500 mt-2">Isso pode levar alguns segundos</p>
        <div id="progressoImportacao" class="mt-4">
            <div class="text-sm text-blue-600">Iniciando extração de texto...</div>
        </div>
    `;
    
    // Ocultar conteúdo e mostrar loading
    conteudoMovimentos.classList.add('hidden');
    modalBody.appendChild(loadingImportacao);
    
    try {
        // Importar peças usando o novo sistema
        for (let i = 0; i < pecasParaImportar.length; i++) {
            const peca = pecasParaImportar[i];
            
            // Atualizar progresso
            const progressoDiv = document.getElementById('progressoImportacao');
            if (progressoDiv) {
                progressoDiv.innerHTML = `
                    <div class="text-sm text-blue-600">
                        <i class="fas fa-spinner fa-spin"></i> 
                        Extraindo texto da peça ${i + 1} de ${pecasParaImportar.length}: ${peca.descricao}
                    </div>
                `;
            }
            
            // Buscar conteúdo real da peça via API
            let conteudoPeca = '';
            try {
                const response = await fetch('/api/buscar_conteudo_peca', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'Accept-Charset': 'utf-8'
                    },
                    body: JSON.stringify({
                        numero_processo: numeroProcesso,
                        id_peca: peca.id,
                        sistema: 'br.jus.jfrj.eproc'
                    })
                });
                
                const resultado = await response.json();
                
                if (resultado.success) {
                    // Criar conteúdo da peça com informações essenciais
                    conteudoPeca = `Evento: ${peca.evento} (${formatarData(peca.data)})\n\n`;
                    
                    // Adicionar texto extraído se disponível
                    if (resultado.texto_extraido && resultado.texto_extraido.trim()) {
                        conteudoPeca += resultado.texto_extraido;
                    } else {
                        conteudoPeca += `${resultado.mensagem}`;
                    }
                } else {
                    // Fallback se não conseguir buscar o conteúdo
                    conteudoPeca = `Evento: ${peca.evento} (${formatarData(peca.data)})\n\n`;
                    conteudoPeca += `[Erro ao buscar conteúdo da peça: ${resultado.error}]`;
                }
                
            } catch (error) {
                // Fallback em caso de erro na API
                conteudoPeca = `Evento: ${peca.evento} (${formatarData(peca.data)})\n\n`;
                conteudoPeca += `[Erro ao buscar conteúdo da peça: ${error.message}]`;
            }
            
            // Criar nova peça usando o novo sistema
            const novaPeca = {
                id: peca.id,
                nome: peca.descricao,
                conteudo: conteudoPeca,
                tipo: 'importada'
            };
            
            pecasImportadas.push(novaPeca);
            const elemento = criarElementoPeca(novaPeca, 'importada', pecasImportadas.length);
            document.getElementById('pecas-container').appendChild(elemento);
        }
        
        // Atualizar ordens e contador
        atualizarOrdens();
        updateContadorPecas();
        
        // Limpar seleção e fechar modal
        movimentosSelecionados.clear();
        atualizarContadorSelecionados();
        fecharModalMovimentos();
        
        // Mostrar mensagem de sucesso
        const totalImportadas = pecasParaImportar.length;
        let mensagem = `Importadas ${totalImportadas} peça(s) com sucesso!`;
        
        mostrarMensagem(mensagem, 'success');
        
    } catch (error) {
        console.error('Erro ao importar peças:', error);
        mostrarMensagem(`Erro ao importar peças: ${error.message}`, 'error');
    } finally {
        // Remover loading e restaurar conteúdo
        const loadingImportacao = document.getElementById('loadingImportacao');
        if (loadingImportacao) {
            loadingImportacao.remove();
        }
        conteudoMovimentos.classList.remove('hidden');
    }
}

// Função para sincronizar seleções do modal com peças existentes
function sincronizarSelecoesModal() {
    const container = document.getElementById('pecas-container');
    const pecasExistentes = container.querySelectorAll('.peca-item');
    const pecasJaImportadas = new Set();
    
    // Coletar IDs das peças que já estão nos grupos de campos
    pecasExistentes.forEach(pecaItem => {
        const nomeInput = pecaItem.querySelector('input[name="peca_nome[]"]');
        if (nomeInput && nomeInput.getAttribute('data-peca-id')) {
            pecasJaImportadas.add(nomeInput.getAttribute('data-peca-id'));
        }
    });
    
    // Limpar seleções atuais
    movimentosSelecionados.clear();
    
    // Marcar apenas as peças que estão nos grupos de campos
    movimentosData.forEach(movimento => {
        if (movimento.pecas) {
            movimento.pecas.forEach(peca => {
                if (pecasJaImportadas.has(peca.id)) {
                    movimentosSelecionados.add(peca.id);
                }
            });
        }
    });
    
    // Atualizar checkboxes no modal
    const checkboxes = document.querySelectorAll('.peca-checkbox');
    checkboxes.forEach(checkbox => {
        const pecaId = checkbox.value;
        checkbox.checked = movimentosSelecionados.has(pecaId);
        
        // Desabilitar checkboxes de peças já importadas
        if (pecasJaImportadas.has(pecaId)) {
            checkbox.disabled = true;
            checkbox.parentElement.style.opacity = '0.5';
        } else {
            checkbox.disabled = false;
            checkbox.parentElement.style.opacity = '1';
        }
    });
    
    // Atualizar checkbox "selecionar todas"
    const selectAll = document.getElementById('selectAll');
    if (selectAll) {
        const checkboxesHabilitados = document.querySelectorAll('.peca-checkbox:not(:disabled)');
        const totalCheckboxes = checkboxesHabilitados.length;
        const checkedCheckboxes = Array.from(checkboxesHabilitados).filter(cb => cb.checked).length;
        selectAll.checked = totalCheckboxes > 0 && checkedCheckboxes === totalCheckboxes;
        selectAll.indeterminate = checkedCheckboxes > 0 && checkedCheckboxes < totalCheckboxes;
    }
    
    // Atualizar contador
    atualizarContadorSelecionados();
    
    // Mostrar informação sobre peças já importadas
    if (pecasJaImportadas.size > 0) {
        const infoDiv = document.createElement('div');
        infoDiv.className = 'mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md';
        infoDiv.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-info-circle text-blue-500 mr-2"></i>
                <span class="text-sm text-blue-700">
                    ${pecasJaImportadas.size} peça(s) já importada(s) - marcadas e desabilitadas
                </span>
            </div>
        `;
        
        // Inserir antes da tabela
        const tabela = document.querySelector('.movimentos-table');
        if (tabela && !document.querySelector('.bg-blue-50')) {
            tabela.parentElement.insertBefore(infoDiv, tabela);
        }
    }
}

// Função para limpar seleção
function limparSelecao() {
    movimentosSelecionados.clear();
    const checkboxes = document.querySelectorAll('.peca-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    atualizarContadorSelecionados();
}

// Função para inverter a ordem dos movimentos
function inverterOrdemMovimentos() {
    if (movimentosData.length === 0) {
        return;
    }
    
    // Inverter o array de movimentos
    movimentosData.reverse();
    
    // Inverter também a ordem das peças dentro de cada movimento
    movimentosData.forEach(movimento => {
        if (movimento.pecas && movimento.pecas.length > 0) {
            movimento.pecas.reverse();
        }
    });
    
    // Alternar o estado da ordem
    ordemInvertida = !ordemInvertida;
    
    // Re-renderizar a tabela
    renderizarMovimentos();
}

// Função para mostrar mensagens
function mostrarMensagem(mensagem, tipo = 'info') {
    // Criar elemento de mensagem
    const mensagemDiv = document.createElement('div');
    mensagemDiv.className = `alert alert-${tipo === 'success' ? 'success' : tipo === 'error' ? 'danger' : 'info'} alert-dismissible fade show`;
    mensagemDiv.innerHTML = `
        ${mensagem}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Inserir no topo da página
    const container = document.querySelector('.space-y-6');
    if (container) {
        container.insertBefore(mensagemDiv, container.firstChild);
        
        // Remover automaticamente após 5 segundos
        setTimeout(() => {
            if (mensagemDiv.parentNode) {
                mensagemDiv.remove();
            }
        }, 5000);
    }
}

// Variáveis globais para visualização de peças
let pecaVisualizadaAtual = null;

// Função para visualizar uma peça específica
async function visualizarPeca(pecaId, rotulo) {
    // Obter número do processo
    const numeroProcesso = document.getElementById('numero_processo').value.trim();
    if (!numeroProcesso) {
        alert('Número do processo é obrigatório para visualizar peças.');
        return;
    }
    
    // Armazenar dados da peça atual
    pecaVisualizadaAtual = {
        id: pecaId,
        rotulo: rotulo,
        numeroProcesso: numeroProcesso
    };
    
    // Mostrar modal de visualização
    abrirModalVisualizarPeca();
    
    // Mostrar loading
    document.getElementById('loadingVisualizarPeca').classList.remove('hidden');
    document.getElementById('conteudoVisualizarPeca').classList.add('hidden');
    document.getElementById('erroVisualizarPeca').classList.add('hidden');
    
    try {
        // Buscar conteúdo da peça
        const response = await fetch('/api/buscar_conteudo_peca', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                numero_processo: numeroProcesso,
                id_peca: pecaId,
                sistema: 'br.jus.jfrj.eproc'
            })
        });
        
        const resultado = await response.json();
        
        // Esconder loading
        document.getElementById('loadingVisualizarPeca').classList.add('hidden');
        
        if (resultado.success) {
            // Preencher informações da peça
            document.getElementById('pecaNome').textContent = rotulo;
            document.getElementById('pecaFormato').textContent = resultado.formato || 'N/A';
            document.getElementById('pecaTamanho').textContent = formatarTamanho(resultado.tamanho_bytes);
            document.getElementById('pecaStatus').textContent = resultado.conteudo_disponivel ? 'Disponível' : 'Indisponível';
            
            // Preencher conteúdo
            const conteudoElement = document.getElementById('pecaConteudo');
            if (resultado.texto_extraido && resultado.texto_extraido.trim()) {
                conteudoElement.textContent = resultado.texto_extraido;
                document.getElementById('btnImportarPeca').classList.remove('hidden');
            } else {
                conteudoElement.textContent = resultado.mensagem || 'Conteúdo não disponível para visualização.';
                document.getElementById('btnImportarPeca').classList.add('hidden');
            }
            
            // Mostrar conteúdo
            document.getElementById('conteudoVisualizarPeca').classList.remove('hidden');
        } else {
            // Mostrar erro
            document.getElementById('mensagemErroVisualizarPeca').textContent = resultado.error || 'Erro desconhecido ao carregar peça.';
            document.getElementById('erroVisualizarPeca').classList.remove('hidden');
        }
    } catch (error) {
        // Esconder loading
        document.getElementById('loadingVisualizarPeca').classList.add('hidden');
        
        // Mostrar erro
        document.getElementById('mensagemErroVisualizarPeca').textContent = `Erro de conexão: ${error.message}`;
        document.getElementById('erroVisualizarPeca').classList.remove('hidden');
    }
}

// Função para abrir modal de visualização
function abrirModalVisualizarPeca() {
    document.getElementById('modalVisualizarPeca').style.display = 'block';
}

// Função para fechar modal de visualização
function fecharModalVisualizarPeca() {
    document.getElementById('modalVisualizarPeca').style.display = 'none';
    pecaVisualizadaAtual = null;
}

// Função para importar peça visualizada
function importarPecaVisualizada() {
    if (!pecaVisualizadaAtual) {
        alert('Nenhuma peça selecionada para importar.');
        return;
    }
    
    // Verificar se a peça já foi importada
    const container = document.getElementById('pecas-container');
    const pecasExistentes = container.querySelectorAll('.peca-item');
    
    for (let pecaItem of pecasExistentes) {
        const pecaId = pecaItem.dataset.pecaId;
        if (pecaId === pecaVisualizadaAtual.id) {
            alert('Esta peça já foi importada.');
            return;
        }
    }
    
    // Obter conteúdo da peça (editado)
    const conteudoElement = document.getElementById('pecaConteudo');
    const conteudo = conteudoElement.innerText;
    
    if (!conteudo || conteudo.trim() === '') {
        alert('Não há conteúdo disponível para importar.');
        return;
    }
    
    // Criar elemento da peça
    const peca = {
        id: pecaVisualizadaAtual.id,
        nome: pecaVisualizadaAtual.rotulo,
        conteudo: conteudo,
        tipo: 'importada'
    };
    
    // Adicionar peça ao container
    const elementoPeca = criarElementoPeca(peca, 'importada');
    container.appendChild(elementoPeca);
    
    // Atualizar contadores
    updateContadorPecas();
    
    // Fechar modal
    fecharModalVisualizarPeca();
    
    // Mostrar notificação
    showNotification('Peça importada com sucesso!', 'success');
}

// Função para formatar tamanho em bytes
function formatarTamanho(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
        
    loadAIModels();
    initializeDragAndDrop();
    initializeCKEditor();
    updateContadorPecas();
    
    // Inicializar textos dinâmicos
    atualizarTextosDinamicos(objetivoAtual);
    
    // Adicionar event listener para mudança de prompt
    const promptSelect = document.getElementById('prompt_select');
    if (promptSelect) {
        promptSelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            if (selectedOption && selectedOption.dataset.aiModel) {
                carregarModeloDoPrompt(selectedOption.dataset.aiModel);
            } else {
                // Se não há modelo associado ao prompt, usar o padrão da aplicação
                loadDefaultModel();
            }
        });
    }
    
    // Carregar prompts iniciais para o objetivo atual
    // Aguardar um pouco para garantir que os modelos foram carregados
    setTimeout(() => {
        carregarPromptsPorObjetivo(objetivoAtual);
    }, 100);
});

// Inicializar sistema de drag and drop
function initializeDragAndDrop() {
    const containers = ['pecas-container', 'outras-pecas-container'];
    
    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) {
            container.addEventListener('dragover', handleDragOver);
            container.addEventListener('drop', handleDrop);
        }
    });
}

// Função para criar elemento de peça com drag and drop
function criarElementoPeca(peca, tipo = 'importada', ordem = null) {
    const pecaId = peca.id || `peca_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const ordemFinal = ordem !== null ? ordem : (tipo === 'importada' ? pecasImportadas.length + 1 : pecasManuais.length + 1);
    
    const elemento = document.createElement('div');
    elemento.className = 'peca-item bg-gray-50 border border-gray-200 rounded-lg p-4';
    elemento.draggable = false; // Não tornar o elemento inteiro draggable
    elemento.dataset.pecaId = pecaId;
    elemento.dataset.tipo = tipo;
    elemento.dataset.ordem = ordemFinal;
    
    elemento.innerHTML = `
        <div class="flex items-start space-x-3">
            <div class="order-indicator">${ordemFinal}</div>
            <div class="drag-handle flex-shrink-0 mt-1" draggable="true">
                <i class="fas fa-grip-vertical text-lg"></i>
            </div>
            <div class="flex-grow">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Nome da Peça</label>
                        <input type="text" name="peca_nome[]" required
                               class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                               placeholder="Ex: Petição Inicial"
                               value="${peca.nome || ''}">
                    </div>
                    <div class="flex items-end justify-between">
                        <span class="text-xs text-gray-500">${tipo === 'importada' ? 'Importada do Eproc' : 'Manual'}</span>
                        <button type="button" onclick="removePeca('${pecaId}')" 
                                class="text-red-600 hover:text-red-800">
                            <i class="fas fa-trash"></i> Remover
                        </button>
                    </div>
                </div>
                <div class="mt-3">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Conteúdo da Peça</label>
                    <textarea name="peca_conteudo[]" rows="4" required
                              class="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                              placeholder="Cole o conteúdo da peça processual...">${peca.conteudo || ''}</textarea>
                </div>
            </div>
        </div>
    `;
    
    // Adicionar event listeners para drag and drop apenas no drag-handle
    const dragHandle = elemento.querySelector('.drag-handle');
    dragHandle.addEventListener('dragstart', handleDragStart);
    dragHandle.addEventListener('dragend', handleDragEnd);
    
    // Event listeners para o elemento pai (para drop e dragover)
    elemento.addEventListener('dragover', handleDragOver);
    elemento.addEventListener('drop', handleDrop);
    
    return elemento;
}

// Event handlers para drag and drop
function handleDragStart(e) {
    // Encontrar o elemento pai (peca-item) do drag-handle
    const pecaItem = e.target.closest('.peca-item');
    if (!pecaItem) return;
    
    dragSource = pecaItem;
    pecaItem.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', pecaItem.outerHTML);
}

function handleDragEnd(e) {
    // Encontrar o elemento pai (peca-item) do drag-handle
    const pecaItem = e.target.closest('.peca-item');
    if (pecaItem) {
        pecaItem.classList.remove('dragging');
    }
    
    dragSource = null;
    dragTarget = null;
    
    // Remover classes de drag over de todos os elementos
    document.querySelectorAll('.peca-item').forEach(item => {
        item.classList.remove('drag-over', 'drag-over-top', 'drag-over-bottom');
    });
    
    // Remover classes de drag over dos containers
    document.querySelectorAll('#pecas-container, #outras-pecas-container').forEach(cont => {
        cont.classList.remove('drag-over-container');
    });
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const pecaItem = e.target.closest('.peca-item');
    const container = e.target.closest('#pecas-container, #outras-pecas-container');
    
    // Remover classes de drag over de todos os elementos
    document.querySelectorAll('.peca-item').forEach(item => {
        item.classList.remove('drag-over', 'drag-over-top', 'drag-over-bottom');
    });
    
    // Remover classes de drag over dos containers
    document.querySelectorAll('#pecas-container, #outras-pecas-container').forEach(cont => {
        cont.classList.remove('drag-over-container');
    });
    
    if (!pecaItem || pecaItem === dragSource) {
        // Mouse está em área vazia do container - inserir no final
        if (container) {
            container.classList.add('drag-over-container');
            dragTarget = { element: container, position: 'end' };
        }
        return;
    }
    
    // Calcular a posição relativa do mouse dentro do elemento
    const rect = pecaItem.getBoundingClientRect();
    const mouseY = e.clientY;
    const elementTop = rect.top;
    const elementBottom = rect.bottom;
    const elementHeight = rect.height;
    const threshold = elementHeight * 0.3; // 30% da altura do elemento
    
    // Determinar se o mouse está na parte superior ou inferior do elemento
    const distanceFromTop = mouseY - elementTop;
    const distanceFromBottom = elementBottom - mouseY;
    
    if (distanceFromTop < threshold) {
        // Mouse está na parte superior - inserir antes
        pecaItem.classList.add('drag-over-top');
        dragTarget = { element: pecaItem, position: 'before' };
    } else if (distanceFromBottom < threshold) {
        // Mouse está na parte inferior - inserir depois
        pecaItem.classList.add('drag-over-bottom');
        dragTarget = { element: pecaItem, position: 'after' };
    } else {
        // Mouse está no meio - inserir antes (comportamento padrão)
        pecaItem.classList.add('drag-over-top');
        dragTarget = { element: pecaItem, position: 'before' };
    }
}

function handleDrop(e) {
    e.preventDefault();
    
    if (!dragSource || !dragTarget) {
        return;
    }
    
    // Verificar se os elementos ainda existem no DOM
    if (!document.contains(dragSource)) {
        return;
    }
    
    // Verificar se é inserção no final do container
    if (dragTarget.position === 'end') {
        const sourceContainer = dragSource.closest('#pecas-container, #outras-pecas-container');
        const targetContainer = dragTarget.element;
        
        if (!sourceContainer || !targetContainer) {
            return;
        }
        
        if (sourceContainer === targetContainer) {
            // Mover para o final do mesmo container
            sourceContainer.removeChild(dragSource);
            sourceContainer.appendChild(dragSource);
        } else {
            // Mover para o final de outro container
            sourceContainer.removeChild(dragSource);
            targetContainer.appendChild(dragSource);
            
            // Atualizar tipo da peça baseado no container
            const novoTipo = targetContainer.id === 'pecas-container' ? 'importada' : 'manual';
            dragSource.dataset.tipo = novoTipo;
            
            // Atualizar indicador visual
            const tipoSpan = dragSource.querySelector('.text-xs.text-gray-500');
            if (tipoSpan) {
                tipoSpan.textContent = novoTipo === 'importada' ? 'Importada do Eproc' : 'Manual';
            }
        }
        
        // Atualizar ordens
        atualizarOrdens();
        return;
    }
    
    if (dragSource === dragTarget.element) {
        return;
    }
    
    const sourceContainer = dragSource.closest('#pecas-container, #outras-pecas-container');
    const targetContainer = dragTarget.element.closest('#pecas-container, #outras-pecas-container');
    
    if (!sourceContainer || !targetContainer) {
        return;
    }
    
    // Verificar se o elemento alvo ainda existe no DOM
    if (!document.contains(dragTarget.element)) {
        return;
    }
    
    // Permitir reordenação dentro do mesmo container
    if (sourceContainer === targetContainer) {
        // Obter todos os elementos antes de fazer qualquer modificação
        const allItems = Array.from(sourceContainer.children);
        const sourceIndex = allItems.indexOf(dragSource);
        const targetIndex = allItems.indexOf(dragTarget.element);
        
        // Verificar se os índices são válidos
        if (sourceIndex === -1 || targetIndex === -1) {
            return;
        }
        
        // Remover o elemento da posição atual
        sourceContainer.removeChild(dragSource);
        
        // Inserir na nova posição
        if (dragTarget.position === 'after') {
            // Inserir depois do elemento alvo
            const nextSibling = dragTarget.element.nextSibling;
            if (nextSibling) {
                sourceContainer.insertBefore(dragSource, nextSibling);
            } else {
                sourceContainer.appendChild(dragSource);
            }
        } else {
            // Inserir antes do elemento alvo
            sourceContainer.insertBefore(dragSource, dragTarget.element);
        }
    } else {
        // Mover entre containers
        const sourceIndex = Array.from(sourceContainer.children).indexOf(dragSource);
        const targetIndex = Array.from(targetContainer.children).indexOf(dragTarget.element);
        
        // Verificar se os índices são válidos
        if (sourceIndex === -1 || targetIndex === -1) {
            return;
        }
        
        // Remover do container original
        sourceContainer.removeChild(dragSource);
        
        // Inserir no novo container
        if (dragTarget.position === 'after') {
            // Inserir depois do elemento alvo
            const nextSibling = dragTarget.element.nextSibling;
            if (nextSibling) {
                targetContainer.insertBefore(dragSource, nextSibling);
            } else {
                targetContainer.appendChild(dragSource);
            }
        } else {
            // Inserir antes do elemento alvo
            targetContainer.insertBefore(dragSource, dragTarget.element);
        }
        
        // Atualizar tipo da peça baseado no container
        const novoTipo = targetContainer.id === 'pecas-container' ? 'importada' : 'manual';
        dragSource.dataset.tipo = novoTipo;
        
        // Atualizar indicador visual
        const tipoSpan = dragSource.querySelector('.text-xs.text-gray-500');
        if (tipoSpan) {
            tipoSpan.textContent = novoTipo === 'importada' ? 'Importada do Eproc' : 'Manual';
        }
    }
    
    // Atualizar ordens
    atualizarOrdens();
}

// Função para atualizar os números de ordem
function atualizarOrdens() {
    const containers = ['pecas-container', 'outras-pecas-container'];
    
    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) {
            const items = Array.from(container.children);
            items.forEach((item, index) => {
                const orderIndicator = item.querySelector('.order-indicator');
                if (orderIndicator) {
                    orderIndicator.textContent = index + 1;
                    item.dataset.ordem = index + 1;
                }
            });
        }
    });
}

// Função para adicionar peça manual
function addPeca() {
    const novaPeca = {
        id: `manual_${Date.now()}`,
        nome: '',
        conteudo: '',
        tipo: 'manual'
    };
    
    pecasManuais.push(novaPeca);
    const elemento = criarElementoPeca(novaPeca, 'manual', pecasManuais.length);
    document.getElementById('outras-pecas-container').appendChild(elemento);
    atualizarOrdens();
    updateContadorPecas();
}

// Função para remover peça
function removePeca(pecaId) {
    // Remover da lista de peças importadas
    pecasImportadas = pecasImportadas.filter(peca => peca.id !== pecaId);
    
    // Remover da lista de peças manuais
    pecasManuais = pecasManuais.filter(peca => peca.id !== pecaId);
    
    // Remover do DOM
    const elemento = document.querySelector(`[data-peca-id="${pecaId}"]`);
    if (elemento) {
        elemento.remove();
    }
    
    atualizarOrdens();
    updateContadorPecas();
}

// Função para importar peças do modal (versão simples - não usada)
function importarPecasSimples() {
    const checkboxes = document.querySelectorAll('#modal-movimentos .movimento-checkbox:checked');
    let pecasImportadasCount = 0;
    let pecasExistentes = 0;
    
    checkboxes.forEach(checkbox => {
        const pecaId = checkbox.value;
        const pecaNome = checkbox.getAttribute('data-peca-nome');
        const pecaConteudo = checkbox.getAttribute('data-peca-conteudo');
        
        // Verificar se a peça já foi importada
        const pecaExistente = document.querySelector(`[data-peca-id="${pecaId}"]`);
        if (pecaExistente) {
            pecasExistentes++;
            return;
        }
        
        const novaPeca = {
            id: pecaId,
            nome: pecaNome,
            conteudo: pecaConteudo,
            tipo: 'importada'
        };
        
        pecasImportadas.push(novaPeca);
        const elemento = criarElementoPeca(novaPeca, 'importada', pecasImportadas.length);
        document.getElementById('pecas-container').appendChild(elemento);
        pecasImportadasCount++;
    });
    
    atualizarOrdens();
    updateContadorPecas();
    
    // Fechar modal
    document.getElementById('modal-movimentos').style.display = 'none';
    
    // Mostrar mensagem de resultado
    let mensagem = '';
    if (pecasImportadasCount > 0) {
        mensagem += `${pecasImportadasCount} peça(s) importada(s) com sucesso. `;
    }
    if (pecasExistentes > 0) {
        mensagem += `${pecasExistentes} peça(s) já existia(m) e foi(ram) ignorada(s).`;
    }
    
    if (mensagem) {
        alert(mensagem);
    }
}

// Função para obter peças ordenadas
function obterPecasOrdenadas() {
    const pecas = [];
    
    // Obter peças do processo (importadas)
    const containerProcesso = document.getElementById('pecas-container');
    if (containerProcesso) {
        const elementos = Array.from(containerProcesso.children);
        elementos.forEach(elemento => {
            const nome = elemento.querySelector('input[name="peca_nome[]"]').value;
            const conteudo = elemento.querySelector('textarea[name="peca_conteudo[]"]').value;
            const ordem = parseInt(elemento.dataset.ordem);
            
            pecas.push({
                nome: nome,
                conteudo: conteudo,
                ordem: ordem,
                tipo: 'importada'
            });
        });
    }
    
    // Obter outras peças (manuais)
    const containerOutras = document.getElementById('outras-pecas-container');
    if (containerOutras) {
        const elementos = Array.from(containerOutras.children);
        elementos.forEach(elemento => {
            const nome = elemento.querySelector('input[name="peca_nome[]"]').value;
            const conteudo = elemento.querySelector('textarea[name="peca_conteudo[]"]').value;
            const ordem = parseInt(elemento.dataset.ordem);
            
            pecas.push({
                nome: nome,
                conteudo: conteudo,
                ordem: ordem,
                tipo: 'manual'
            });
        });
    }
    
    // Ordenar por ordem
    return pecas.sort((a, b) => a.ordem - b.ordem);
}

// Função para atualizar contador de peças
function updateContadorPecas() {
    const containerProcesso = document.getElementById('pecas-container');
    const containerOutras = document.getElementById('outras-pecas-container');
    
    const totalPecasProcesso = containerProcesso ? containerProcesso.children.length : 0;
    const totalPecasOutras = containerOutras ? containerOutras.children.length : 0;
    const totalPecas = totalPecasProcesso + totalPecasOutras;
    
    const contadorElement = document.getElementById('contador-pecas');
    if (contadorElement) {
        contadorElement.textContent = totalPecas;
    }
}

// Função para mostrar preview da ordem das peças
function mostrarPreviewOrdem() {
    const pecasOrdenadas = obterPecasOrdenadas();
    
    if (pecasOrdenadas.length === 0) {
        alert('Não há peças para mostrar.');
        return;
    }
    
    let preview = 'Ordem das peças que serão enviadas:\n\n';
    pecasOrdenadas.forEach((peca, index) => {
        preview += `${index + 1}. ${peca.nome} (${peca.tipo})\n`;
    });
    
    alert(preview);
}

// Função para enviar formulário
async function enviarFormulario() {
    const submitBtn = document.querySelector('button[onclick="enviarFormulario()"]');
    if (!submitBtn) {
        console.error('Botão de envio não encontrado');
        showNotification('Erro: botão de envio não encontrado', 'error');
        return;
    }
    
    const originalText = submitBtn.innerHTML;
    
    // Desabilitar botão e mostrar loading
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Gerando...';
    
    try {
        // Coletar dados do formulário
        const formData = {
            numero_processo: document.getElementById('numero_processo').value,
            objetivo: objetivoAtual,
            pecas_processuais: [],
            prompt_id: document.getElementById('prompt_select').value,
            ai_model_id: document.getElementById('ai_model_select').value
        };
        
        // Adicionar campos específicos baseados no objetivo
        if (objetivoAtual === 'minuta') {
            formData.como_decidir = document.getElementById('como_decidir').value;
            formData.fundamentos = document.getElementById('fundamentos').value;
            formData.vedacoes = document.getElementById('vedacoes').value;
        } else {
            formData.instrucoes_adicionais = document.getElementById('instrucoes_adicionais').value;
        }
    
    // Obter peças ordenadas
    const pecasOrdenadas = obterPecasOrdenadas();
    
    // Validar se há peças
    if (pecasOrdenadas.length === 0) {
            showNotification('Por favor, adicione pelo menos uma peça processual.', 'error');
        return;
    }
    
        // Adicionar peças ao formData
        formData.pecas_processuais = pecasOrdenadas.map(peca => ({
            nome: peca.nome,
            conteudo: peca.conteudo
        }));
        
        // Enviar para o servidor com timeout de 5 minutos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 minutos
        
        const response = await fetch('/generate_minuta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        const result = await response.json();
        
        if (response.ok) {
            // Salvar dados do formulário para uso em ajustes
            currentFormData = formData;
            
            // Obter o resultado (pode ser 'minuta' ou 'resultado')
            const resultado = result.minuta || result.resultado;
            
            if (!resultado) {
                showNotification('Erro: Nenhum resultado recebido do servidor', 'error');
                return;
            }
            
            // Converter o texto para HTML formatado
            const formattedResult = formatMinutaToHtml(resultado);
            
            // Mostrar resultado
            const resultadoDiv = document.getElementById('resultado');
            
            resultadoDiv.classList.remove('hidden');
            
            // Inicializar CKEditor se ainda não foi inicializado
            if (!editor) {
                initializeCKEditor();
                // Aguardar um pouco para o CKEditor ser inicializado
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            
            // Definir o conteúdo no editor
            if (editor) {
                editor.setData(formattedResult);
            }
            
            
            // Mostrar informações de tokens e custos se disponíveis
            if (result.tokens_info || result.cost_info) {
                const tokensInfo = result.tokens_info || {};
                const costInfo = result.cost_info || {};
                
                let tokensHtml = `
                    <div class="mt-4 p-3 bg-gray-50 rounded-lg">
                        <h4 class="text-sm font-medium text-gray-700 mb-2">
                            <i class="fas fa-chart-bar mr-2"></i>Informações de Tokens
                        </h4>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
                            <div class="text-center">
                                <div class="font-medium text-purple-600">${tokensInfo.total_tokens || 0}</div>
                                <div class="text-gray-500">Total Tokens</div>
                            </div>
                            <div class="text-center">
                                <div class="font-medium text-blue-600">${tokensInfo.request_tokens || 0}</div>
                                <div class="text-gray-500">Envio</div>
                            </div>
                            <div class="text-center">
                                <div class="font-medium text-green-600">${tokensInfo.response_tokens || 0}</div>
                                <div class="text-gray-500">Resposta</div>
                            </div>
                            <div class="text-center">
                                <div class="font-medium text-gray-600">${tokensInfo.model_used || 'N/A'}</div>
                                <div class="text-gray-500">Modelo</div>
                            </div>
                        </div>`;
                
                // Adicionar custo simplificado se disponível
                if (result.user_cost) {
                    tokensHtml += `
                        <div class="border-t border-gray-200 pt-3">
                            <div class="text-center">
                                <div class="text-lg font-bold text-red-600">${result.user_cost}</div>
                                <div class="text-xs text-gray-500">Custo Estimado</div>
                            </div>
                        </div>`;
                } else if (costInfo && costInfo.total_cost_usd) {
                    // Fallback: converter USD para BRL (aproximado)
                    const costUsd = parseFloat(costInfo.total_cost_usd.replace('$', ''));
                    const costBrl = (costUsd * 5.5).toFixed(2).replace('.', ',');
                    
                    tokensHtml += `
                        <div class="border-t border-gray-200 pt-3">
                            <div class="text-center">
                                <div class="text-lg font-bold text-red-600">R$ ${costBrl}</div>
                                <div class="text-xs text-gray-500">Custo Estimado</div>
                            </div>
                        </div>`;
                }
                
                tokensHtml += `
                        ${tokensInfo.success ? 
                            '<div class="mt-2 text-center"><span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"><i class="fas fa-check mr-1"></i>Sucesso</span></div>' :
                            '<div class="mt-2 text-center"><span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800"><i class="fas fa-times mr-1"></i>Erro</span></div>'
                        }
                    </div>`;
                
                document.getElementById('tokens-info').innerHTML = tokensHtml;
            }
            
            // Scroll para o resultado
            document.getElementById('resultado').scrollIntoView({ behavior: 'smooth' });
            
            showNotification('Minuta gerada com sucesso!', 'success');
        } else {
            showNotification('Erro ao gerar minuta: ' + result.error, 'error');
        }
        
    } catch (error) {
        console.error('Erro:', error);
        showNotification('Erro ao gerar minuta. Tente novamente.', 'error');
    } finally {
        // Restaurar botão
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// Função para copiar minuta
function copiarMinuta() {
    if (!editor) {
        showNotification('Editor não inicializado', 'error');
        return;
    }
    
    // Obter o conteúdo HTML do editor
    const htmlContent = editor.getData();
    
    // Função para copiar HTML usando Clipboard API moderna
    const copyHtmlToClipboard = async () => {
        try {
            // Criar um objeto ClipboardItem com HTML
            const clipboardItem = new ClipboardItem({
                'text/html': new Blob([htmlContent], { type: 'text/html' }),
                'text/plain': new Blob([editor.getData().replace(/<[^>]*>/g, '')], { type: 'text/plain' })
            });
            
            await navigator.clipboard.write([clipboardItem]);
            return true;
        } catch (err) {
            console.log('Clipboard API não suportada, tentando método alternativo');
            return false;
        }
    };
    
    // Função para copiar usando método alternativo
    const copyUsingExecCommand = () => {
        // Criar um elemento temporário
        const tempElement = document.createElement('div');
        tempElement.style.position = 'absolute';
        tempElement.style.left = '-9999px';
        tempElement.style.top = '-9999px';
        tempElement.innerHTML = htmlContent;
        document.body.appendChild(tempElement);
        
        // Selecionar o conteúdo
        const range = document.createRange();
        range.selectNodeContents(tempElement);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        
        try {
            // Tentar copiar
            const success = document.execCommand('copy');
            selection.removeAllRanges();
            document.body.removeChild(tempElement);
            return success;
        } catch (err) {
            selection.removeAllRanges();
            document.body.removeChild(tempElement);
            return false;
        }
    };
    
    // Função para copiar como texto simples
    const copyAsPlainText = async () => {
        try {
            const textContent = editor.getData().replace(/<[^>]*>/g, '');
            await navigator.clipboard.writeText(textContent);
            return true;
        } catch (err) {
            return false;
        }
    };
    
    // Executar a cópia com fallbacks
    copyHtmlToClipboard().then(success => {
        if (!success) {
            return copyUsingExecCommand();
        }
        return success;
    }).then(success => {
        if (!success) {
            return copyAsPlainText();
        }
        return success;
    }).then(success => {
        if (success) {
            showNotification('Conteúdo copiado com sucesso!', 'success');
        } else {
            showNotification('Erro ao copiar conteúdo!', 'error');
        }
    });
}

// Função para baixar minuta
function baixarMinuta() {
    if (!editor) {
        showNotification('Editor não inicializado', 'error');
        return;
    }
    
    const htmlContent = editor.getData();
    
    if (!htmlContent || htmlContent.trim() === '') {
        showNotification('Nenhum conteúdo para baixar!', 'error');
        return;
    }
    
    try {
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = window.URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `minuta_${new Date().toISOString().slice(0, 10)}.html`;
        document.body.appendChild(a);
        a.click();
        
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Minuta baixada com sucesso!', 'success');
    } catch (error) {
        console.error('Erro ao baixar minuta:', error);
        showNotification('Erro ao baixar minuta!', 'error');
    }
}

// Função para inicializar CKEditor
function initializeCKEditor() {
    
    const editorContainer = document.querySelector('#editor');
    
    if (!editorContainer) {
        console.warn('Container do CKEditor não encontrado. Será inicializado quando o resultado for exibido.');
        return;
    }
    
    ClassicEditor
        .create(editorContainer, {
            toolbar: {
                items: [
                    'heading',
                    '|',
                    'bold',
                    'italic',
                    '|',
                    'indent',
                    'outdent',
                    '|',
                    'blockQuote',
                    '|',
                    'undo',
                    'redo'
                ]
            },
            language: 'pt-br',
            placeholder: 'A minuta será exibida aqui após a geração...'
        })
        .then(newEditor => {
            editor = newEditor;
        })
        .catch(error => {
            console.error('🔍 [DEBUG] Erro ao inicializar CKEditor:', error);
        });
}

// Função para carregar modelos de IA
function loadAIModels() {
    const modelSelect = document.getElementById('ai_model_select');
    
    // Limpar opções existentes
    modelSelect.innerHTML = '';
    
    // Carregar modelos da API
    fetch('/api/available_models')
        .then(response => response.json())
        .then(data => {
            // Adicionar opções
            // Filtrar apenas modelos ativos (se a API retornar essa informação)
            const activeModels = data.models.filter(model => {
                // Se o modelo tem campo 'active', usar ele; senão, assumir que está ativo
                return model.active !== false && model.status !== 'inactive';
            });
            
            activeModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                modelSelect.appendChild(option);
            });
            
            // Carregar modelo default
            loadDefaultModel();
        })
        .catch(error => {
            console.error('Erro ao carregar modelos:', error);
            // Fallback para modelos hardcoded
            loadHardcodedModels();
        });
}

// Função para carregar modelo padrão
function loadDefaultModel() {
    fetch('/api/default_model')
        .then(response => response.json())
        .then(data => {
            const modelSelect = document.getElementById('ai_model_select');
            const defaultOption = modelSelect.querySelector(`option[value="${data.default_model}"]`);
            if (defaultOption) {
                defaultOption.selected = true;
            }
        })
        .catch(error => {
            console.error('Erro ao carregar modelo default:', error);
            // Selecionar primeira opção como fallback
            const modelSelect = document.getElementById('ai_model_select');
            if (modelSelect.options.length > 0) {
                modelSelect.selectedIndex = 0;
            }
        });
}

// Função para carregar modelos hardcoded como fallback
function loadHardcodedModels() {
    const modelSelect = document.getElementById('ai_model_select');
    
    // Modelos disponíveis como fallback
    const availableModels = [
        { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro (Google)' },
        { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash (Google)' },
        { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4 (Anthropic)' },
        { id: 'claude-3-7-sonnet-20250219', name: 'Claude Sonnet 3.7 (Anthropic)' },
        { id: 'o3-2025-04-16', name: 'O3 (OpenAI)' },
        { id: 'o4-mini-2025-04-16', name: 'O4 Mini (OpenAI)' }
    ];
    
    // Adicionar opções
    availableModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = model.name;
        modelSelect.appendChild(option);
    });
    
    // Selecionar modelo default
    const defaultModel = 'gemini-2.5-pro';
    const defaultOption = modelSelect.querySelector(`option[value="${defaultModel}"]`);
    if (defaultOption) {
        defaultOption.selected = true;
    }
}

// Função para formatar minuta para HTML
function formatMinutaToHtml(text) {
    if (!text || text.trim() === '') {
        return '<p>Nenhum conteúdo disponível.</p>';
    }
    
    // Converter quebras de linha em parágrafos
    let html = text
        .replace(/\n\n+/g, '</p><p>')  // Múltiplas quebras de linha viram parágrafos
        .replace(/\n/g, '<br>');       // Quebras simples viram <br>
    
    // Adicionar tags de parágrafo no início e fim
    html = '<p>' + html + '</p>';
    
    // Formatar títulos (linhas que terminam com ":")
    html = html.replace(/<p>([^:]+:)<\/p>/g, '<h2>$1</h2>');
    
    // Formatar palavras em negrito (entre **)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Formatar palavras em itálico (entre *)
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    
    // Formatar sublinhado (entre __)
    html = html.replace(/__([^_]+)__/g, '<u>$1</u>');
    
    // Formatar tachado (entre ~~)
    html = html.replace(/~~([^~]+)~~/g, '<s>$1</s>');
    
    // Formatar listas numeradas
    html = html.replace(/<p>(\d+\.\s+[^<]+)<\/p>/g, '<ol><li>$1</li></ol>');
    
    // Formatar listas com marcadores
    html = html.replace(/<p>[-*]\s+([^<]+)<\/p>/g, '<ul><li>$1</li></ul>');
    
    // Formatar citações (linhas que começam com >)
    html = html.replace(/<p>&gt;\s+([^<]+)<\/p>/g, '<blockquote><p>$1</p></blockquote>');
    
    // Formatar código inline (entre `)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Limpar parágrafos vazios
    html = html.replace(/<p><\/p>/g, '');
    
    // Limpar tags vazias
    html = html.replace(/<(h2|ol|ul|blockquote)><\/\1>/g, '');
    
    // Adicionar espaçamento entre elementos
    html = html.replace(/<\/h2>/g, '</h2><br>');
    html = html.replace(/<\/ol>/g, '</ol><br>');
    html = html.replace(/<\/ul>/g, '</ul><br>');
    html = html.replace(/<\/blockquote>/g, '</blockquote><br>');
    
    return html;
}

// Função para mostrar notificação
function showNotification(message, type = 'info') {
    // Criar elemento de notificação
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-md shadow-lg max-w-sm transform transition-all duration-300 translate-x-full`;
    
    // Definir cores baseadas no tipo
    switch(type) {
        case 'success':
            notification.className += ' bg-green-50 border border-green-200 text-green-800';
            notification.innerHTML = `<div class="flex"><i class="fas fa-check-circle mr-2"></i><span>${message}</span></div>`;
            break;
        case 'error':
            notification.className += ' bg-red-50 border border-red-200 text-red-800';
            notification.innerHTML = `<div class="flex"><i class="fas fa-exclamation-circle mr-2"></i><span>${message}</span></div>`;
            break;
        case 'warning':
            notification.className += ' bg-yellow-50 border border-yellow-200 text-yellow-800';
            notification.innerHTML = `<div class="flex"><i class="fas fa-exclamation-triangle mr-2"></i><span>${message}</span></div>`;
            break;
        default:
            notification.className += ' bg-blue-50 border border-blue-200 text-blue-800';
            notification.innerHTML = `<div class="flex"><i class="fas fa-info-circle mr-2"></i><span>${message}</span></div>`;
    }
    
    // Adicionar ao DOM
    document.body.appendChild(notification);
    
    // Animar entrada
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);
    
    // Remover após 5 segundos
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

// ===== FUNÇÕES DE AJUSTES E VERSÕES =====

let versionCounter = 0;
let editors = {}; // Armazenar múltiplos editores

function showAdjustDialog() {
    
    // Verificar se há conteúdo no editor principal
    if (!editor) {
        console.log('🔍 [DEBUG] Editor não inicializado');
        showNotification('Gere uma minuta primeiro antes de solicitar ajustes.', 'warning');
        return;
    }
    
    const editorData = editor.getData();
    
    if (!editorData.trim()) {
        console.log('🔍 [DEBUG] Editor sem conteúdo, mostrando warning');
        showNotification('Gere uma minuta primeiro antes de solicitar ajustes.', 'warning');
        return;
    }
    
    
    // Carregar modelos de IA no modal
    loadAIModelsForAdjust();
    
    // Mostrar modal
    const modal = document.getElementById('adjustModal');
    
    modal.classList.remove('hidden');
    
        // Focar no campo de ajuste
    setTimeout(() => {
        const adjustPrompt = document.getElementById('adjustPrompt');
        if (adjustPrompt) {
            adjustPrompt.focus();
        }
    }, 100);
}

function hideAdjustDialog() {
    document.getElementById('adjustModal').classList.add('hidden');
    document.getElementById('adjustPrompt').value = '';
}

function loadAIModelsForAdjust() {
    
    const adjustModelSelect = document.getElementById('adjustModel');
    
    adjustModelSelect.innerHTML = '';
    
    // Carregar modelos disponíveis
    fetch('/api/available_models')
        .then(response => response.json())
        .then(data => {
            
            // Acessar o array de modelos dentro do objeto retornado
            const models = data.models || [];
            
            // Filtrar apenas modelos ativos (se a API retornar essa informação)
            const activeModels = models.filter(model => {
                // Se o modelo tem campo 'active', usar ele; senão, assumir que está ativo
                return model.active !== false && model.status !== 'inactive';
            });
            
            activeModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                adjustModelSelect.appendChild(option);
            });
            
            // Selecionar modelo default
            return fetch('/api/default_model');
        })
        .then(response => response.json())
        .then(defaultData => {
            
            // Acessar o ID do modelo default dentro do objeto retornado
            const defaultModelId = defaultData.default_model || defaultData.id;
            
            const defaultOption = adjustModelSelect.querySelector(`option[value="${defaultModelId}"]`);
            if (defaultOption) {
                defaultOption.selected = true;
            } else {
                if (adjustModelSelect.options.length > 0) {
                    adjustModelSelect.selectedIndex = 0;
                }
            }
        })
        .catch(error => {
            console.error('🔍 [DEBUG] Erro ao carregar modelos para ajuste:', error);
            // Fallback para modelos hardcoded
            const availableModels = [
                { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro (Google)' },
                { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash (Google)' },
                { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4 (Anthropic)' },
                { id: 'claude-3-7-sonnet-20250219', name: 'Claude Sonnet 3.7 (Anthropic)' },
                { id: 'o3-2025-04-16', name: 'O3 (OpenAI)' },
                { id: 'o4-mini-2025-04-16', name: 'O4 Mini (OpenAI)' }
            ];
            
            availableModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                adjustModelSelect.appendChild(option);
            });
            
            // Selecionar modelo default
            const defaultOption = adjustModelSelect.querySelector('option[value="gemini-2.5-pro"]');
            if (defaultOption) {
                defaultOption.selected = true;
            }
        });
}

async function requestAdjustment() {
    const adjustPrompt = document.getElementById('adjustPrompt').value.trim();
    const adjustModel = document.getElementById('adjustModel').value;
    
    if (!adjustPrompt) {
        showNotification('Por favor, descreva o ajuste desejado.', 'error');
        return;
    }
    
    if (!currentFormData) {
        showNotification('Erro: dados do formulário não encontrados.', 'error');
        return;
    }
    
    // Desabilitar botão e mostrar loading
    const requestBtn = document.getElementById('requestAdjustBtn');
    const originalText = requestBtn.innerHTML;
    requestBtn.disabled = true;
    requestBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processando...';
    
    try {
        // Obter o conteúdo atual do editor principal
        const currentContent = editor ? editor.getData() : '';
        
                // Preparar dados para o ajuste
        const adjustmentData = {
            ...currentFormData,
            objetivo: objetivoAtual,
            adjustment_prompt: adjustPrompt,
            current_content: currentContent,
            model_id: adjustModel
        };
        
        // Enviar para o servidor com timeout de 5 minutos
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 minutos
        
        const response = await fetch('/adjust_minuta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(adjustmentData),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        const result = await response.json();
        
        
        if (response.ok) {
            // Obter o resultado (pode ser 'minuta' ou 'resultado')
            const resultado = result.minuta || result.resultado;
            
            if (!resultado) {
                showNotification('Erro: Nenhum resultado recebido do servidor', 'error');
                return;
            }
            
            // Criar nova versão
            createNewVersion(resultado, adjustPrompt, result.tokens_info, result.cost_info, result.user_cost);
            
            // Fechar modal
            hideAdjustDialog();
            
            // Mostrar seção de ajustes
            showAdjustsSection();
            
            showNotification('Ajuste aplicado com sucesso!', 'success');
        } else {
            showNotification('Erro: ' + result.error, 'error');
        }
        
    } catch (error) {
        console.error('Erro:', error);
        showNotification('Erro ao solicitar ajuste. Tente novamente.', 'error');
    } finally {
        // Restaurar botão
        requestBtn.disabled = false;
        requestBtn.innerHTML = originalText;
    }
}

function createNewVersion(content, adjustmentPrompt, tokensInfo, costInfo, user_cost = null) {
    versionCounter++;
    const versionId = `version-${versionCounter}`;
    
    // Atualizar contador na interface
    document.getElementById('version-counter').textContent = versionCounter;
    
    // Criar container da versão
    const versionContainer = document.createElement('div');
    versionContainer.id = versionId;
    versionContainer.className = 'bg-gray-50 border border-gray-200 rounded-lg p-4';
    
    // Criar header da versão
    const versionHeader = document.createElement('div');
    versionHeader.className = 'flex items-center justify-between mb-4';
    versionHeader.innerHTML = `
        <div>
            <h4 class="text-md font-medium text-gray-900">
                <i class="fas fa-edit mr-2 text-blue-600"></i>
                Versão ${versionCounter} - Ajuste
            </h4>
            <p class="text-sm text-gray-600 mt-1">
                <strong>Solicitação:</strong> ${adjustmentPrompt}
            </p>
        </div>
        <div class="flex space-x-2">
            <button onclick="copyVersionContent('${versionId}')" 
                    class="inline-flex items-center px-2 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                <i class="fas fa-copy mr-1"></i>
                Copiar
            </button>
            <button onclick="downloadVersion('${versionId}')" 
                    class="inline-flex items-center px-2 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                <i class="fas fa-download mr-1"></i>
                Baixar
            </button>
            <button onclick="removeVersion('${versionId}')" 
                    class="inline-flex items-center px-2 py-1 border border-red-300 shadow-sm text-xs font-medium rounded-md text-red-700 bg-red-50 hover:bg-red-100">
                <i class="fas fa-trash mr-1"></i>
                Remover
            </button>
            <button onclick="useVersionAsBase('${versionId}')" 
                    class="inline-flex items-center px-2 py-1 border border-green-300 shadow-sm text-xs font-medium rounded-md text-green-700 bg-green-50 hover:bg-green-100">
                <i class="fas fa-arrow-up mr-1"></i>
                Usar como Base
            </button>
        </div>
    `;
    
    // Criar container do editor
    const editorContainer = document.createElement('div');
    editorContainer.className = 'mb-4';
    editorContainer.innerHTML = `<div id="editor-${versionId}"></div>`;
    
    // Criar informações de tokens e custo simplificado
    const tokensContainer = document.createElement('div');
    tokensContainer.className = 'p-3 bg-white rounded-lg border';
    
    let tokensHtml = `
        <h5 class="text-sm font-medium text-gray-700 mb-2">
            <i class="fas fa-chart-bar mr-2"></i>Informações de Tokens
        </h5>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
            <div class="text-center">
                <div class="font-medium text-purple-600">${tokensInfo.total_tokens || 0}</div>
                <div class="text-gray-500">Total Tokens</div>
            </div>
            <div class="text-center">
                <div class="font-medium text-blue-600">${tokensInfo.request_tokens || 0}</div>
                <div class="text-gray-500">Envio</div>
            </div>
            <div class="text-center">
                <div class="font-medium text-green-600">${tokensInfo.response_tokens || 0}</div>
                <div class="text-gray-500">Resposta</div>
            </div>
            <div class="text-center">
                <div class="font-medium text-gray-600">${tokensInfo.model_used || 'N/A'}</div>
                <div class="text-gray-500">Modelo</div>
            </div>
        </div>`;
    
    // Adicionar custo simplificado se disponível
    if (user_cost) {
        tokensHtml += `
        <div class="border-t border-gray-200 pt-3">
            <div class="text-center">
                <div class="text-lg font-bold text-red-600">${user_cost}</div>
                <div class="text-xs text-gray-500">Custo Estimado</div>
            </div>
        </div>`;
    } else if (costInfo && costInfo.total_cost_usd) {
        // Fallback: converter USD para BRL (aproximado)
        const costUsd = parseFloat(costInfo.total_cost_usd.replace('$', ''));
        const costBrl = (costUsd * 5.5).toFixed(2).replace('.', ',');
        
        tokensHtml += `
        <div class="border-t border-gray-200 pt-3">
            <div class="text-center">
                <div class="text-lg font-bold text-red-600">R$ ${costBrl}</div>
                <div class="text-xs text-gray-500">Custo Estimado</div>
            </div>
        </div>`;
    }
    
    // Adicionar badge de sucesso
    tokensHtml += `
        ${tokensInfo.success ? 
            '<div class="mt-2 text-center"><span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"><i class="fas fa-check mr-1"></i>Sucesso</span></div>' :
            '<div class="mt-2 text-center"><span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800"><i class="fas fa-times mr-1"></i>Erro</span></div>'
        }
    `;
    
    tokensContainer.innerHTML = tokensHtml;
    
    // Montar versão completa
    versionContainer.appendChild(versionHeader);
    versionContainer.appendChild(editorContainer);
    versionContainer.appendChild(tokensContainer);
    
    // Adicionar ao container de versões
    document.getElementById('versoes-container').appendChild(versionContainer);
    
    // Inicializar CKEditor para esta versão
    ClassicEditor
        .create(document.querySelector(`#editor-${versionId}`), {
            toolbar: {
                items: [
                    'heading',
                    '|',
                    'bold',
                    'italic',
                    '|',
                    'indent',
                    'outdent',
                    '|',
                    'blockQuote',
                    '|',
                    'undo',
                    'redo'
                ]
            },
            language: 'pt-br',
            placeholder: 'Conteúdo da versão...'
        })
        .then(newEditor => {
            editors[versionId] = newEditor;
            // Formatar o conteúdo como HTML antes de definir no editor
            const formattedContent = formatMinutaToHtml(content);
            newEditor.setData(formattedContent);
        })
        .catch(error => {
            console.error('Erro ao inicializar CKEditor para versão:', error);
        });
}

function showAdjustsSection() {
    // Mostrar a seção de ajustes
    document.getElementById('ajustes-section').classList.remove('hidden');
    
    // Scroll para a seção
    document.getElementById('ajustes-section').scrollIntoView({ behavior: 'smooth' });
}

function hideAdjustsSection() {
    // Esconder a seção de ajustes
    document.getElementById('ajustes-section').classList.add('hidden');
}

function copyVersionContent(versionId) {
    const versionEditor = editors[versionId];
    if (!versionEditor) {
        showNotification('Editor não encontrado para esta versão.', 'error');
        return;
    }
    
    const content = versionEditor.getData();
    
    // Tentar copiar usando Clipboard API
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(content).then(() => {
            showNotification('Conteúdo copiado para a área de transferência!', 'success');
        }).catch(() => {
            // Fallback para método antigo
            copyUsingExecCommand(content);
        });
    } else {
        // Fallback para método antigo
        copyUsingExecCommand(content);
    }
}

function copyUsingExecCommand(content) {
    const textArea = document.createElement('textarea');
    textArea.value = content;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showNotification('Conteúdo copiado para a área de transferência!', 'success');
    } catch (err) {
        showNotification('Erro ao copiar conteúdo.', 'error');
    }
    
    document.body.removeChild(textArea);
}

function downloadVersion(versionId) {
    const versionEditor = editors[versionId];
    if (!versionEditor) {
        showNotification('Editor não encontrado para esta versão.', 'error');
        return;
    }
    
    const content = versionEditor.getData();
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `minuta-versao-${versionId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Arquivo baixado com sucesso!', 'success');
}

function removeVersion(versionId) {
    if (confirm('Tem certeza que deseja remover esta versão?')) {
        const versionElement = document.getElementById(versionId);
        if (versionElement) {
            // Destruir editor se existir
            if (editors[versionId]) {
                editors[versionId].destroy();
                delete editors[versionId];
            }
            
            versionElement.remove();
            versionCounter--;
            document.getElementById('version-counter').textContent = versionCounter;
            
            showNotification('Versão removida com sucesso!', 'success');
        }
    }
}

function useVersionAsBase(versionId) {
    const versionEditor = editors[versionId];
    if (!versionEditor) {
        showNotification('Editor não encontrado para esta versão.', 'error');
        return;
    }
    
    const content = versionEditor.getData();
    
    // Atualizar editor principal
    if (editor) {
        editor.setData(content);
        
        // Mostrar resultado
        document.getElementById('resultado').classList.remove('hidden');
        document.getElementById('resultado').scrollIntoView({ behavior: 'smooth' });
        
        showNotification('Versão aplicada como base no editor principal!', 'success');
    }
}

function clearAllVersions() {
    if (confirm('Tem certeza que deseja remover todas as versões?')) {
        // Destruir todos os editores
        Object.keys(editors).forEach(versionId => {
            if (editors[versionId]) {
                editors[versionId].destroy();
            }
        });
        
        // Limpar container
        document.getElementById('versoes-container').innerHTML = '';
        
        // Resetar contador
        versionCounter = 0;
        document.getElementById('version-counter').textContent = '0';
        
        // Esconder seção
        hideAdjustsSection();
        
        showNotification('Todas as versões foram removidas!', 'success');
    }
}