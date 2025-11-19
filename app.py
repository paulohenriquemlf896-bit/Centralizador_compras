from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = 'chave_secreta_segura'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banco_dados.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS (TABELAS) ---

class Loja(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    funcao = db.Column(db.String(20), nullable=False) 
    verificado = db.Column(db.Boolean, default=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=True)
    loja = db.relationship('Loja', backref=db.backref('usuarios', lazy=True))

class Periodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)      
    grupo_filtro = db.Column(db.String(50), nullable=False) 
    data_limite = db.Column(db.Date, nullable=False)
    
    # NOVAS COLUNAS DE CALENDÁRIO
    mes = db.Column(db.Integer, nullable=False) # Ex: 1 (Janeiro)
    ano = db.Column(db.Integer, nullable=False) # Ex: 2025
    
    ativo = db.Column(db.Boolean, default=True)

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    laboratorio = db.Column(db.String(100), nullable=False)
    grupo = db.Column(db.String(50), default='2.1')       
    unidade_caixa = db.Column(db.Integer, default=1)
    preco = db.Column(db.Float, default=0.00) 

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_alteracao = db.Column(db.DateTime, default=datetime.now) 
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.id'), nullable=False) 
    periodo = db.relationship('Periodo')
    status = db.Column(db.String(20), default='Aberto') 

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    produto = db.relationship('Produto') 

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard_admin' if session.get('funcao') == 'Admin' else 'dashboard_loja'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = request.args.get('erro')
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email).first()
        
        if user and user.senha == senha:
            if not user.verificado:
                erro = 'Sua conta ainda não foi aprovada pelo Administrador.'
            else:
                session['usuario_id'] = user.id
                session['nome'] = user.nome
                session['funcao'] = user.funcao
                session['loja_id'] = user.loja_id 
                return redirect(url_for('dashboard_admin' if user.funcao == 'Admin' else 'dashboard_loja'))
        else:
            erro = 'Email ou senha incorretos.'
    return render_template('login.html', erro=erro)

@app.route('/cadastro', methods=['GET', 'POST'])
def register():
    lojas = Loja.query.all()
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        funcao = request.form['funcao']
        loja_id = request.form.get('loja_id')
        
        if Usuario.query.filter_by(email=email).first():
            return render_template('register.html', lojas=lojas, erro="E-mail já cadastrado!")
        
        if funcao == 'Admin': loja_id = None
        elif loja_id: loja_id = int(loja_id)
        else: return render_template('register.html', lojas=lojas, erro="Selecione uma loja.")

        novo = Usuario(nome=nome, email=email, senha=senha, funcao=funcao, loja_id=loja_id, verificado=False)
        db.session.add(novo)
        db.session.commit()
        return redirect(url_for('login', erro="Cadastro realizado! Aguarde aprovação."))

    return render_template('register.html', lojas=lojas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROTAS DO ADMIN ---

@app.route('/admin/usuarios')
def admin_usuarios():
    if 'usuario_id' not in session or session.get('funcao') != 'Admin': return redirect(url_for('login'))
    usuarios = Usuario.query.order_by(Usuario.verificado.asc(), Usuario.nome.asc()).all()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/aprovar/<int:user_id>')
def aprovar_usuario(user_id):
    if 'usuario_id' not in session or session.get('funcao') != 'Admin': return redirect(url_for('login'))
    user = Usuario.query.get(user_id)
    if user:
        user.verificado = True
        db.session.commit()
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/excluir/<int:user_id>')
def excluir_usuario(user_id):
    if 'usuario_id' not in session or session.get('funcao') != 'Admin': return redirect(url_for('login'))
    if user_id == session['usuario_id']: return redirect(url_for('admin_usuarios'))
    user = Usuario.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin_usuarios'))

# --- ROTAS DA LOJA ---

@app.route('/dashboard/loja')
def dashboard_loja():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    # Mostra apenas períodos ativos (futuros ou presentes)
    # A lógica de criação automática garante que tenhamos os períodos certos aqui
    periodos = Periodo.query.filter_by(ativo=True).order_by(Periodo.data_limite).all()
    
    info_periodos = []
    for p in periodos:
        pedido = Pedido.query.filter_by(usuario_id=session['usuario_id'], 
                                      loja_id=session['loja_id'], 
                                      periodo_id=p.id).order_by(Pedido.id.desc()).first()
        
        status = "Pendente"
        cor = "danger"
        detalhe = "Toque para iniciar"
        
        if pedido:
            if pedido.status == 'Enviado':
                status = "Enviado"
                cor = "success"
                detalhe = f"Enviado em {pedido.data_alteracao.strftime('%d/%m %H:%M')}"
            else:
                status = "Em Andamento"
                cor = "warning text-dark"
                detalhe = "Continuar editando..."
        
        info_periodos.append({
            'id': p.id,
            'nome': p.nome,
            'limite': p.data_limite.strftime('%d/%m/%Y'), # Data completa
            'status': status,
            'cor': cor,
            'detalhe': detalhe
        })

    return render_template('dashboard_loja.html', nome=session['nome'], periodos=info_periodos)

@app.route('/pedido/selecao-fabricante/<int:periodo_id>')
def selecao_fabricante(periodo_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    periodo = Periodo.query.get_or_404(periodo_id)
    laboratorios_db = db.session.query(Produto.laboratorio).filter_by(grupo=periodo.grupo_filtro).distinct().all()
    
    lista_final = []
    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], 
                                        loja_id=session['loja_id'], 
                                        periodo_id=periodo.id).order_by(Pedido.id.desc()).first()

    data_formatada = ""
    if pedido_atual and pedido_atual.data_alteracao:
        data_formatada = pedido_atual.data_alteracao.strftime('%d/%m às %H:%M')

    for lab in laboratorios_db:
        nome_lab = lab[0]
        status = 'nao_iniciado'
        qtd_itens = 0

        if pedido_atual:
            filtro_status = 'concluido' if pedido_atual.status == 'Enviado' else 'andamento'
            qtd_itens = db.session.query(ItemPedido).join(Produto).filter(
                ItemPedido.pedido_id == pedido_atual.id,
                Produto.laboratorio == nome_lab
            ).count()

            if qtd_itens > 0: status = filtro_status
            elif pedido_atual.status == 'Enviado': status = 'concluido'

        lista_final.append({
            'nome': nome_lab, 'status': status, 'itens': qtd_itens, 'data_hora': data_formatada 
        })

    return render_template('fabricantes.html', lista_fabricantes=lista_final, periodo=periodo)

@app.route('/pedido/form/<int:periodo_id>/<laboratorio>', methods=['GET', 'POST'])
def pedido_form(periodo_id, laboratorio):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    periodo = Periodo.query.get_or_404(periodo_id)
    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], 
                                        loja_id=session['loja_id'], 
                                        periodo_id=periodo.id, 
                                        status='Aberto').first()
    
    if not pedido_atual:
        verif_enviado = Pedido.query.filter_by(usuario_id=session['usuario_id'], periodo_id=periodo.id, status='Enviado').first()
        if verif_enviado: return redirect(url_for('selecao_fabricante', periodo_id=periodo.id))

        pedido_atual = Pedido(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=periodo.id, status='Aberto')
        db.session.add(pedido_atual)
        db.session.commit()

    if request.method == 'POST':
        try:
            for key, value in request.form.items():
                if key.startswith('qtd_'):
                    prod_id = int(key.split('_')[1])
                    try: qtd = int(value)
                    except: qtd = 0
                    
                    item = ItemPedido.query.filter_by(pedido_id=pedido_atual.id, produto_id=prod_id).first()
                    if item:
                        if qtd > 0: item.quantidade = qtd
                        else: db.session.delete(item)
                    elif qtd > 0:
                        db.session.add(ItemPedido(pedido_id=pedido_atual.id, produto_id=prod_id, quantidade=qtd))
            
            pedido_atual.data_alteracao = datetime.now()
            db.session.commit()
            
            if request.form.get('acao') == 'finalizar':
                pedido_atual.status = 'Enviado'
                db.session.commit()
            
            return redirect(url_for('selecao_fabricante', periodo_id=periodo.id))
        except Exception as e:
            db.session.rollback()
            return f"Erro: {str(e)}"

    produtos = Produto.query.filter_by(laboratorio=laboratorio, grupo=periodo.grupo_filtro).order_by(Produto.nome).all()
    itens_salvos = {}
    if pedido_atual:
        itens = ItemPedido.query.filter_by(pedido_id=pedido_atual.id).all()
        for i in itens: itens_salvos[i.produto_id] = i.quantidade

    return render_template('pedido_form.html', 
                         produtos=produtos, 
                         nome_periodo=periodo.nome, 
                         laboratorio_atual=laboratorio,
                         itens_salvos=itens_salvos,
                         periodo_id=periodo.id)

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    # 1. PREPARAÇÃO DO FILTRO DE MESES
    # Pega todos os períodos para montar o dropdown de opções (ex: Nov/2025, Dez/2025)
    todos_periodos = Periodo.query.order_by(Periodo.ano.desc(), Periodo.mes.desc()).all()
    opcoes_meses = []
    meses_vistos = set()
    
    # Dicionário para nome dos meses em Português
    nomes_meses = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 
                   7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}

    for p in todos_periodos:
        chave = f"{p.mes}-{p.ano}" # Ex: "11-2025"
        if chave not in meses_vistos:
            opcoes_meses.append({
                'valor': chave,
                'texto': f"{nomes_meses[p.mes]}/{p.ano}"
            })
            meses_vistos.add(chave)
    
    # 2. APLICA O FILTRO (SE O USUÁRIO ESCOLHEU ALGUM)
    filtro_atual = request.args.get('filtro_data') # Vem da URL ?filtro_data=11-2025
    
    query = Periodo.query
    if filtro_atual:
        mes_f, ano_f = filtro_atual.split('-')
        query = query.filter_by(mes=int(mes_f), ano=int(ano_f))
    
    # Ordena para mostrar os mais recentes primeiro
    periodos_filtrados = query.order_by(Periodo.ano.desc(), Periodo.mes.desc(), Periodo.data_limite).all()
    
    # 3. MONTA OS DADOS DO PAINEL (IGUAL ANTES, MAS USANDO A LISTA FILTRADA)
    todas_lojas = Loja.query.all()
    dados_painel = []

    for p in periodos_filtrados:
        status_lojas = []
        for loja in todas_lojas:
            pedido = Pedido.query.filter_by(loja_id=loja.id, periodo_id=p.id).order_by(Pedido.id.desc()).first()
            info = { 'nome': loja.nome, 'cor': 'danger', 'texto': '⏳ Pendente', 'detalhe': 'Não iniciou' }
            
            if pedido:
                if pedido.status == 'Enviado':
                    info.update({'cor': 'success', 'texto': '✅ Finalizado', 'detalhe': f"Enviado {pedido.data_alteracao.strftime('%d/%m')}"})
                elif pedido.status == 'Aberto':
                    qtd = ItemPedido.query.filter_by(pedido_id=pedido.id).count()
                    if qtd > 0: info.update({'cor': 'warning text-dark', 'texto': '✏️ Editando', 'detalhe': 'Em andamento'})
            
            status_lojas.append(info)
        
        dados_painel.append({'periodo': p, 'lojas': status_lojas})

    return render_template('dashboard_admin.html', 
                           nome=session['nome'], 
                           dados_painel=dados_painel, 
                           opcoes_meses=opcoes_meses, # Envia opções pro HTML
                           filtro_atual=filtro_atual, # Envia a escolha atual pro HTML
                           data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route('/admin/consolidacao')
def consolidacao_pedidos():
    if 'usuario_id' not in session or session.get('funcao') != 'Admin': return redirect(url_for('login'))
    
    lojas = Loja.query.all()
    produtos = Produto.query.order_by(Produto.laboratorio, Produto.nome).all()
    dados_agrupados = {}

    for p in produtos:
        if p.laboratorio not in dados_agrupados: dados_agrupados[p.laboratorio] = []
        def get_qtd_loja(nome_loja_parcial):
            loja_encontrada = next((l for l in lojas if nome_loja_parcial.lower() in l.nome.lower()), None)
            if not loja_encontrada: return 0
            resultado = db.session.query(db.func.sum(ItemPedido.quantidade)).join(Pedido).filter(ItemPedido.produto_id == p.id, Pedido.loja_id == loja_encontrada.id).scalar()
            return resultado if resultado else 0

        qtd_campina = get_qtd_loja("Campina")
        qtd_maceio = get_qtd_loja("Maceió")
        qtd_recife = get_qtd_loja("Recife")
        qtd_natal = get_qtd_loja("Natal")
        qtd_pesqueira = get_qtd_loja("Pesqueira")
        total = qtd_campina + qtd_maceio + qtd_recife + qtd_natal + qtd_pesqueira
        dados_agrupados[p.laboratorio].append({
            'nome': p.nome, 'caixa': p.unidade_caixa, 'preco': p.preco,
            'campina': qtd_campina, 'maceio': qtd_maceio, 'recife': qtd_recife, 'natal': qtd_natal, 'pesqueira': qtd_pesqueira, 'total': total
        })
    return render_template('consolidacao.html', dados=dados_agrupados)

# --- FUNÇÃO INTELIGENTE DE GERAÇÃO DE PERÍODOS ---
def gerar_periodos_automaticamente():
    """
    Verifica a data de hoje.
    Se hoje já passou do limite do mês atual, cria o período para o MÊS SEGUINTE.
    Se ainda não passou, cria/garante o período para o MÊS ATUAL.
    """
    hoje = date.today()
    
    # Definição das regras de negócio (Dia limite de cada grupo)
    regras = [
        # (Nome Base, Grupo, Dia Limite)
        ("Diversos", "DIVERSOS", 1),
        ("Medicamentos 2.1", "2.1", 10),
        ("Medicamentos 2.2", "2.2", 17)
    ]

    print(f"--- Verificando Períodos para {hoje.strftime('%d/%m/%Y')} ---")

    for nome_base, grupo, dia_limite in regras:
        # 1. Define para qual mês/ano vamos criar o período
        # Se hoje (ex: dia 12) já passou do limite (ex: dia 10), o pedido agora é para o Mês Que Vem.
        if hoje.day > dia_limite:
            # Lógica para pegar o próximo mês
            if hoje.month == 12:
                mes_alvo = 1
                ano_alvo = hoje.year + 1
            else:
                mes_alvo = hoje.month + 1
                ano_alvo = hoje.year
        else:
            # Ainda está no prazo, é para este mês mesmo
            mes_alvo = hoje.month
            ano_alvo = hoje.year
        
        # 2. Cria o nome amigável (Ex: "Nov/2025")
        data_alvo_obj = date(ano_alvo, mes_alvo, dia_limite)
        nome_mes = data_alvo_obj.strftime("%b/%Y") # Ex: Nov/2025
        nome_completo = f"{nome_base} - {nome_mes}"
        
        # 3. Verifica se já existe no banco para não duplicar
        periodo_existente = Periodo.query.filter_by(grupo_filtro=grupo, mes=mes_alvo, ano=ano_alvo).first()
        
        if not periodo_existente:
            novo_periodo = Periodo(
                nome=nome_completo,
                grupo_filtro=grupo,
                data_limite=data_alvo_obj,
                mes=mes_alvo,
                ano=ano_alvo,
                ativo=True
            )
            db.session.add(novo_periodo)
            print(f"✅ Criado novo período: {nome_completo}")
        else:
            print(f"ℹ️ Período já existe: {nome_completo}")

    db.session.commit()

# --- SETUP INICIAL ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not Loja.query.first():
            print("Criando Lojas e Usuários...")
            l1, l2, l3, l4 = Loja(nome="Campina Grande"), Loja(nome="Maceió"), Loja(nome="Recife"), Loja(nome="Pesqueira")
            db.session.add_all([l1, l2, l3, l4])
            u1 = Usuario(nome="Miguel", email="miguel@loja.com", senha="1234", funcao="Loja", loja=l1, verificado=True)
            u2 = Usuario(nome="Comprador", email="admin@central.com", senha="1234", funcao="Admin", verificado=True)
            db.session.add_all([u1, u2])
            db.session.commit()

        # Cadastra produtos com grupos
        prods_2_1 = [("Cevamec 1% 50ml", "CEVA BOVINO", 12), ("Mogidex 100ml", "OUROFINO", 12)]
        for nome, lab, cx in prods_2_1:
            if not Produto.query.filter_by(nome=nome).first():
                db.session.add(Produto(nome=nome, laboratorio=lab, unidade_caixa=cx, grupo='2.1'))

        prods_2_2 = [("Adethor 250ml", "FABIANI", 4), ("Ferrodex B12 50ml", "FABIANI", 4)]
        for nome, lab, cx in prods_2_2:
            if not Produto.query.filter_by(nome=nome).first():
                db.session.add(Produto(nome=nome, laboratorio=lab, unidade_caixa=cx, grupo='2.2'))
        
        p_div = Produto.query.filter_by(nome="Papel A4").first()
        if not p_div: db.session.add(Produto(nome="Papel A4", laboratorio="SUPRIMENTOS", unidade_caixa=10, grupo='DIVERSOS'))
        
        db.session.commit()

        # RODA A MÁGICA DOS PERÍODOS
        gerar_periodos_automaticamente()

    app.run(debug=True)