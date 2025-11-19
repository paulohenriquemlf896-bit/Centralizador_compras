from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    verificado = db.Column(db.Boolean, default=False) # Segurança
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=True)
    loja = db.relationship('Loja', backref=db.backref('usuarios', lazy=True))

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    laboratorio = db.Column(db.String(100), nullable=False)
    unidade_caixa = db.Column(db.Integer, default=1)
    preco = db.Column(db.Float, default=0.00) 

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_alteracao = db.Column(db.DateTime, default=datetime.now) 
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=False) 
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
    # Captura mensagem de erro/sucesso da URL (ex: vinda do cadastro)
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
        
        if Usuario.query.filter_by(email=email).first():
            return render_template('register.html', lojas=lojas, erro="Este e-mail já está cadastrado!")
        
        loja_id = request.form.get('loja_id')
        if funcao == 'Admin':
            loja_id = None
        elif loja_id:
            loja_id = int(loja_id)
        else:
            return render_template('register.html', lojas=lojas, erro="Por favor, selecione uma loja.")

        # Cria usuário bloqueado (verificado=False)
        novo_usuario = Usuario(nome=nome, email=email, senha=senha, funcao=funcao, loja_id=loja_id, verificado=False)
        db.session.add(novo_usuario)
        db.session.commit()
        
        # Redireciona para login com mensagem
        return redirect(url_for('login', erro="Cadastro realizado! Aguarde a aprovação do Administrador para entrar."))

    return render_template('register.html', lojas=lojas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ROTAS DE GESTÃO DE USUÁRIOS (ADMIN) ---

@app.route('/admin/usuarios')
def admin_usuarios():
    if 'usuario_id' not in session or session.get('funcao') != 'Admin':
        return redirect(url_for('login'))
    
    usuarios = Usuario.query.order_by(Usuario.verificado.asc(), Usuario.nome.asc()).all()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@app.route('/admin/aprovar/<int:user_id>')
def aprovar_usuario(user_id):
    if 'usuario_id' not in session or session.get('funcao') != 'Admin':
        return redirect(url_for('login'))
    
    user = Usuario.query.get(user_id)
    if user:
        user.verificado = True
        db.session.commit()
    
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/excluir/<int:user_id>')
def excluir_usuario(user_id):
    if 'usuario_id' not in session or session.get('funcao') != 'Admin':
        return redirect(url_for('login'))
    
    if user_id == session['usuario_id']: # Evita auto-exclusão
        return redirect(url_for('admin_usuarios'))

    user = Usuario.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    
    return redirect(url_for('admin_usuarios'))


# --- ROTAS DA LOJA ---

@app.route('/dashboard/loja')
def dashboard_loja():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'])\
                         .order_by(Pedido.id.desc()).first()
    return render_template('dashboard_loja.html', nome=session['nome'], pedido=pedido_atual)

@app.route('/pedido/selecao-fabricante')
def selecao_fabricante():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    laboratorios_db = db.session.query(Produto.laboratorio).distinct().all()
    lista_final = []

    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'])\
                         .order_by(Pedido.id.desc()).first()

    data_formatada = ""
    if pedido_atual and pedido_atual.data_alteracao:
        data_formatada = pedido_atual.data_alteracao.strftime('%d/%m às %H:%M')

    for lab in laboratorios_db:
        nome_lab = lab[0]
        status = 'nao_iniciado'
        qtd_itens = 0

        if pedido_atual:
            if pedido_atual.status == 'Enviado':
                status = 'concluido'
                qtd_itens = db.session.query(ItemPedido).join(Produto).filter(
                    ItemPedido.pedido_id == pedido_atual.id,
                    Produto.laboratorio == nome_lab
                ).count()
            else:
                qtd_itens = db.session.query(ItemPedido).join(Produto).filter(
                    ItemPedido.pedido_id == pedido_atual.id,
                    Produto.laboratorio == nome_lab
                ).count()

                if qtd_itens > 0:
                    status = 'andamento'

        lista_final.append({
            'nome': nome_lab, 
            'status': status, 
            'itens': qtd_itens,
            'data_hora': data_formatada 
        })

    return render_template('fabricantes.html', lista_fabricantes=lista_final)

@app.route('/pedido/form/<laboratorio>', methods=['GET', 'POST'])
def pedido_form(laboratorio):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'], status='Aberto').first()
    
    if not pedido_atual:
        pedido_atual = Pedido(usuario_id=session['usuario_id'], loja_id=session['loja_id'], status='Aberto')
        db.session.add(pedido_atual)
        db.session.commit()

    if request.method == 'POST':
        try:
            for key, value in request.form.items():
                if key.startswith('qtd_'):
                    prod_id = int(key.split('_')[1])
                    try:
                        qtd = int(value)
                    except ValueError:
                        qtd = 0
                    
                    item_existente = ItemPedido.query.filter_by(pedido_id=pedido_atual.id, produto_id=prod_id).first()
                    
                    if item_existente:
                        if qtd > 0:
                            item_existente.quantidade = qtd
                        else:
                            db.session.delete(item_existente)
                    elif qtd > 0:
                        novo_item = ItemPedido(pedido_id=pedido_atual.id, produto_id=prod_id, quantidade=qtd)
                        db.session.add(novo_item)
            
            pedido_atual.data_alteracao = datetime.now()
            db.session.commit()
            
            acao = request.form.get('acao')
            if acao == 'finalizar':
                pedido_atual.status = 'Enviado'
                db.session.commit()
            
            return redirect(url_for('selecao_fabricante'))

        except Exception as e:
            db.session.rollback()
            return f"Erro: {str(e)}"

    produtos = Produto.query.filter_by(laboratorio=laboratorio).order_by(Produto.nome).all()
    
    itens_salvos = {}
    if pedido_atual:
        itens = ItemPedido.query.filter_by(pedido_id=pedido_atual.id).all()
        for i in itens:
            itens_salvos[i.produto_id] = i.quantidade

    return render_template('pedido_form.html', 
                         produtos=produtos, 
                         nome_periodo="Medicamentos 2.1", 
                         laboratorio_atual=laboratorio,
                         itens_salvos=itens_salvos)

# --- ROTAS DO ADMIN ---

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    todas_lojas = Loja.query.all()
    lista_status = []

    for loja in todas_lojas:
        pedido = Pedido.query.filter_by(loja_id=loja.id).order_by(Pedido.id.desc()).first()
        
        info = { 'nome': loja.nome, 'cor': 'danger', 'texto': '⏳ Pendente', 'detalhe': 'Ainda não iniciou' }

        if pedido:
            if pedido.status == 'Enviado':
                info['cor'] = 'success'
                info['texto'] = '✅ Finalizado'
                if pedido.data_alteracao:
                    info['detalhe'] = f"Enviado em {pedido.data_alteracao.strftime('%d/%m às %H:%M')}"
            elif pedido.status == 'Aberto':
                qtd_itens = ItemPedido.query.filter_by(pedido_id=pedido.id).count()
                if qtd_itens > 0:
                    info['cor'] = 'warning text-dark'
                    info['texto'] = '✏️ Em andamento'
                    if pedido.data_alteracao:
                        info['detalhe'] = f"Editando... (últ: {pedido.data_alteracao.strftime('%d/%m %H:%M')})"
                else:
                    info['detalhe'] = 'Aberto mas vazio'

        lista_status.append(info)

    return render_template('dashboard_admin.html', 
                           nome=session['nome'], 
                           status_lojas=lista_status, 
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

# --- SETUP INICIAL ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # SE NÃO TIVER LOJAS, CRIA DADOS PADRÃO
        if not Loja.query.first():
            print("Criando dados iniciais...")
            l1 = Loja(nome="Campina Grande")
            l2 = Loja(nome="Maceió")
            l3 = Loja(nome="Recife")
            l4 = Loja(nome="Pesqueira") 
            db.session.add_all([l1, l2, l3, l4])
            
            # CRIANDO USUÁRIOS INICIAIS (JÁ APROVADOS)
            u1 = Usuario(nome="Miguel", email="miguel@loja.com", senha="1234", funcao="Loja", loja=l1, verificado=True)
            u2 = Usuario(nome="Comprador", email="admin@central.com", senha="1234", funcao="Admin", verificado=True)
            db.session.add_all([u1, u2])
            
            # PRODUTOS CEVA
            prods_ceva = [
                ("Cevamec 1% 50ml", 12, 15.90),
                ("Cevamec 1% 500ml", 6, 45.50),
                ("Estrepto 20ml", 24, 8.20)
            ]
            for nome, caixa, preco in prods_ceva:
                db.session.add(Produto(nome=nome, laboratorio="CEVA BOVINO", unidade_caixa=caixa, preco=preco))

            # PRODUTOS OUROFINO
            prods_ouro = [
                ("Mogidex 100ml", 12, 25.90),
                ("Ourotetra 50ml", 24, 12.50)
            ]
            for nome, caixa, preco in prods_ouro:
                db.session.add(Produto(nome=nome, laboratorio="OUROFINO", unidade_caixa=caixa, preco=preco))
            
            db.session.commit()

        # ADIÇÃO DA FABIANI (VERIFICAÇÃO PARA EVITAR DUPLICIDADE)
        # Lista completa da Fabiani
        prods_fabiani = [
            ("Adethor 250ml", 4, 0.00),
            ("Ferrodex B12 50ml", 4, 0.00),
            ("Ferrodex 250ml", 12, 0.00),
            ("Ferrodex 50ml", 4, 0.00),
            ("Ferrodex 10ml", 24, 0.00),
            ("Paracurso 10ml", 12, 0.00),
            ("Prolacton 10ml", 56, 0.00),
            ("Proverme Sachê 28g", 24, 0.00),
            ("Tormicina 100 50ml", 12, 0.00),
            ("Tormicina 101 10ml", 10, 0.00),
            ("Tormicina L.A 50ml", 24, 0.00),
            ("Vitagold Potenciado 1.000ml", 20, 0.00),
            ("Vitagold Potenciado 250ml", 100, 0.00),
            ("Vitagold Potenciado 50ml", 8, 0.00),
            ("Vitagold Potenciado 20ml", 24, 0.00)
        ]
        
        novos = 0
        for nome, caixa, preco in prods_fabiani:
            if not Produto.query.filter_by(nome=nome, laboratorio="FABIANI").first():
                db.session.add(Produto(nome=nome, laboratorio="FABIANI", unidade_caixa=caixa, preco=preco))
                novos += 1
        
        if novos > 0:
            db.session.commit()
            print(f"{novos} produtos FABIANI adicionados!")

    app.run(debug=True)