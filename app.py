from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'chave_secreta_segura'

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banco_dados.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS ---

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
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=False)
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
    status = db.Column(db.String(20), default='Aberto') 

class ItemPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    produto = db.relationship('Produto') 

class Negociacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.id'), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'), nullable=False)
    desconto = db.Column(db.Float, default=0.0)
    bonificacao = db.Column(db.Float, default=0.0)

class Observacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.id'), nullable=False)
    laboratorio = db.Column(db.String(100), nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=True) 
    texto = db.Column(db.Text, nullable=True)

# --- MÁGICA 24 HORAS: GESTÃO AUTOMÁTICA DE DATAS ---
@app.before_request
def verificar_datas_e_periodos():
    if request.endpoint and 'static' in request.endpoint:
        return

    hoje = date.today()
    regras = [("Diversos", "DIVERSOS", 1), ("Medicamentos 2.1", "2.1", 10), ("Medicamentos 2.2", "2.2", 17)]
    mudou_algo = False

    periodos_abertos = Periodo.query.filter_by(ativo=True).all()
    for p in periodos_abertos:
        if hoje > p.data_limite:
            p.ativo = False
            mudou_algo = True

    for nome_base, grupo, dia_limite in regras:
        if hoje.day > dia_limite:
            mes_alvo, ano_alvo = (1, hoje.year + 1) if hoje.month == 12 else (hoje.month + 1, hoje.year)
        else:
            mes_alvo, ano_alvo = hoje.month, hoje.year
        
        try: data_alvo_obj = date(ano_alvo, mes_alvo, dia_limite)
        except: data_alvo_obj = date(ano_alvo, mes_alvo, 28)

        nome_completo = f"{nome_base} - {data_alvo_obj.strftime('%b/%Y')}"
        
        if not Periodo.query.filter_by(grupo_filtro=grupo, mes=mes_alvo, ano=ano_alvo).first():
            novo = Periodo(nome=nome_completo, grupo_filtro=grupo, data_limite=data_alvo_obj, mes=mes_alvo, ano=ano_alvo, ativo=True)
            db.session.add(novo)
            mudou_algo = True
            
            anterior = Periodo.query.filter(Periodo.grupo_filtro==grupo, Periodo.data_limite < data_alvo_obj, Periodo.ativo==True).first()
            if anterior: anterior.ativo = False

    if mudou_algo: db.session.commit()


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
                erro = 'Conta aguardando aprovação.'
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
        
        if Usuario.query.filter_by(email=email).first(): return render_template('register.html', lojas=lojas, erro="E-mail já existe!")
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

# --- ROTAS LOJA ---

@app.route('/dashboard/loja')
def dashboard_loja():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    periodos = Periodo.query.filter_by(ativo=True).order_by(Periodo.data_limite).all()
    info_periodos = []
    
    for p in periodos:
        pedido = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=p.id).order_by(Pedido.id.desc()).first()
        status, cor, detalhe = "Pendente", "danger", "Toque para iniciar"
        if pedido:
            if pedido.status == 'Enviado': status, cor, detalhe = "Enviado", "success", f"Enviado em {pedido.data_alteracao.strftime('%d/%m %H:%M')}"
            else: status, cor, detalhe = "Em Andamento", "warning text-dark", "Continuar editando..."
        info_periodos.append({'id': p.id, 'nome': p.nome, 'limite': p.data_limite.strftime('%d/%m/%Y'), 'status': status, 'cor': cor, 'detalhe': detalhe})
    
    return render_template('dashboard_loja.html', nome=session['nome'], periodos=info_periodos)

@app.route('/pedido/selecao-fabricante/<int:periodo_id>')
def selecao_fabricante(periodo_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    periodo = Periodo.query.get_or_404(periodo_id)
    laboratorios_db = db.session.query(Produto.laboratorio).filter_by(grupo=periodo.grupo_filtro).distinct().all()
    lista_final = []
    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=periodo.id).order_by(Pedido.id.desc()).first()
    data_formatada = pedido_atual.data_alteracao.strftime('%d/%m às %H:%M') if pedido_atual and pedido_atual.data_alteracao else ""
    
    for lab in laboratorios_db:
        nome_lab = lab[0]
        status, qtd_itens = 'nao_iniciado', 0
        if pedido_atual:
            qtd_itens = db.session.query(ItemPedido).join(Produto).filter(ItemPedido.pedido_id == pedido_atual.id, Produto.laboratorio == nome_lab).count()
            if qtd_itens > 0: status = 'concluido' if pedido_atual.status == 'Enviado' else 'andamento'
            elif pedido_atual.status == 'Enviado': status = 'concluido'
        lista_final.append({'nome': nome_lab, 'status': status, 'itens': qtd_itens, 'data_hora': data_formatada})
    return render_template('fabricantes.html', lista_fabricantes=lista_final, periodo=periodo)

@app.route('/pedido/form/<int:periodo_id>/<laboratorio>', methods=['GET', 'POST'])
def pedido_form(periodo_id, laboratorio):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    periodo = Periodo.query.get_or_404(periodo_id)
    
    if not periodo.ativo and session.get('funcao') != 'Admin':
        return redirect(url_for('dashboard_loja'))

    pedido_atual = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=periodo.id, status='Aberto').first()
    
    if not pedido_atual:
        verif = Pedido.query.filter_by(usuario_id=session['usuario_id'], periodo_id=periodo.id, status='Enviado').first()
        if verif: return redirect(url_for('selecao_fabricante', periodo_id=periodo.id))
        
        if periodo.ativo:
            pedido_atual = Pedido(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=periodo.id, status='Aberto')
            db.session.add(pedido_atual)
            db.session.commit()
        else:
             return redirect(url_for('dashboard_loja'))

    if request.method == 'POST':
        try:
            for key, value in request.form.items():
                if key.startswith('qtd_'):
                    try:
                        prod_id = int(key.split('_')[1])
                        qtd = int(value)
                        item = ItemPedido.query.filter_by(pedido_id=pedido_atual.id, produto_id=prod_id).first()
                        if item:
                            if qtd > 0: item.quantidade = qtd
                            else: db.session.delete(item)
                        elif qtd > 0:
                            db.session.add(ItemPedido(pedido_id=pedido_atual.id, produto_id=prod_id, quantidade=qtd))
                    except: pass
            pedido_atual.data_alteracao = datetime.now()
            db.session.commit()
            # REMOVIDO BOTÃO DE FINALIZAR DAQUI, AGORA VOLTA APENAS
            return redirect(url_for('selecao_fabricante', periodo_id=periodo.id))
        except Exception as e: return f"Erro: {str(e)}"

    produtos = Produto.query.filter_by(laboratorio=laboratorio, grupo=periodo.grupo_filtro).order_by(Produto.nome).all()
    itens = ItemPedido.query.filter_by(pedido_id=pedido_atual.id).all()
    itens_salvos = {i.produto_id: i.quantidade for i in itens}
    return render_template('pedido_form.html', produtos=produtos, nome_periodo=periodo.nome, laboratorio_atual=laboratorio, itens_salvos=itens_salvos, periodo_id=periodo.id)

# --- NOVA ROTA DE FINALIZAÇÃO ---
@app.route('/pedido/finalizar/<int:periodo_id>', methods=['POST'])
def finalizar_pedido_periodo(periodo_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    pedido = Pedido.query.filter_by(usuario_id=session['usuario_id'], loja_id=session['loja_id'], periodo_id=periodo_id, status='Aberto').first()
    
    if pedido:
        qtd = ItemPedido.query.filter_by(pedido_id=pedido.id).count()
        if qtd > 0:
            pedido.status = 'Enviado'
            pedido.data_alteracao = datetime.now()
            db.session.commit()
    
    return redirect(url_for('dashboard_loja'))

# --- ROTAS ADMIN ---

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    todos_periodos = Periodo.query.order_by(Periodo.ano.desc(), Periodo.mes.desc(), Periodo.id.desc()).all()
    opcoes_meses = []
    meses_vistos = set()
    nomes = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    for p in todos_periodos:
        k = f"{p.mes}-{p.ano}"
        if k not in meses_vistos:
            opcoes_meses.append({'valor': k, 'texto': f"{nomes[p.mes]}/{p.ano}"})
            meses_vistos.add(k)
    
    filtro = request.args.get('filtro_data')
    q = Periodo.query
    if filtro:
        m, a = filtro.split('-')
        q = q.filter_by(mes=int(m), ano=int(a))
    
    periodos_filt = q.order_by(Periodo.ano.desc(), Periodo.mes.desc(), Periodo.data_limite).all()
    todas_lojas = Loja.query.all()
    dados_painel = []

    for p in periodos_filt:
        sl = []
        for loja in todas_lojas:
            ped = Pedido.query.filter_by(loja_id=loja.id, periodo_id=p.id).order_by(Pedido.id.desc()).first()
            inf = {'nome': loja.nome, 'cor': 'danger', 'texto': '⏳', 'detalhe': 'Pendente'}
            if ped:
                if ped.status == 'Enviado': inf.update({'cor': 'success', 'texto': '✅', 'detalhe': f"Enviado {ped.data_alteracao.strftime('%d/%m')}"})
                elif ped.status == 'Aberto':
                    q = ItemPedido.query.filter_by(pedido_id=ped.id).count()
                    if q > 0: inf.update({'cor': 'warning text-dark', 'texto': '✏️', 'detalhe': 'Editando'})
            sl.append(inf)
        dados_painel.append({'periodo': p, 'lojas': sl})

    return render_template('dashboard_admin.html', nome=session['nome'], dados_painel=dados_painel, opcoes_meses=opcoes_meses, filtro_atual=filtro, data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route('/admin/consolidacao')
def consolidacao_pedidos():
    if 'usuario_id' not in session or session.get('funcao') != 'Admin': return redirect(url_for('login'))
    
    periodo_ativo = Periodo.query.filter_by(ativo=True).order_by(Periodo.data_limite).first()
    if not periodo_ativo: periodo_ativo = Periodo.query.order_by(Periodo.id.desc()).first()
    if not periodo_ativo: return "Nenhum período."

    lojas = Loja.query.order_by(Loja.nome).all()
    produtos = Produto.query.filter_by(grupo=periodo_ativo.grupo_filtro).order_by(Produto.laboratorio, Produto.nome).all()
    dados = {}

    for p in produtos:
        if p.laboratorio not in dados: dados[p.laboratorio] = []
        negoc = Negociacao.query.filter_by(periodo_id=periodo_ativo.id, produto_id=p.id).first()
        
        qtds_lojas = {}
        total_prod = 0
        for loja in lojas:
            qtd = db.session.query(db.func.sum(ItemPedido.quantidade)).join(Pedido).filter(
                ItemPedido.produto_id == p.id, Pedido.loja_id == loja.id, Pedido.periodo_id == periodo_ativo.id
            ).scalar() or 0
            qtds_lojas[loja.id] = qtd
            total_prod += qtd

        dados[p.laboratorio].append({
            'id': p.id, 'nome': p.nome, 'caixa': p.unidade_caixa, 'preco': p.preco,
            'qtds': qtds_lojas, 'total': total_prod,
            'desconto': negoc.desconto if negoc else 0.0,
            'bonificacao': negoc.bonificacao if negoc else 0.0
        })
    
    obs_db = Observacao.query.filter_by(periodo_id=periodo_ativo.id).all()
    obs_map = {}
    for o in obs_db:
        chave = f"{o.laboratorio}|{o.loja_id if o.loja_id else 'GERAL'}"
        obs_map[chave] = o.texto

    return render_template('consolidacao.html', dados=dados, periodo=periodo_ativo, lojas=lojas, obs_map=obs_map)

@app.route('/api/salvar_item_pedido', methods=['POST'])
def api_salvar_item_pedido():
    if 'usuario_id' not in session: 
        return jsonify({'erro': 'Não logado'}), 401
    
    data = request.json
    periodo_id = data.get('periodo_id')
    produto_id = data.get('produto_id')
    
    try:
        quantidade = int(data.get('quantidade'))
    except:
        quantidade = 0

    if not all([periodo_id, produto_id]):
        return jsonify({'erro': 'Dados incompletos'}), 400

    try:
        # 1. Busca ou Cria o Pedido (Igual fizemos no Admin)
        pedido = Pedido.query.filter_by(
            usuario_id=session['usuario_id'], 
            loja_id=session['loja_id'], 
            periodo_id=periodo_id, 
            status='Aberto'
        ).first()

        if not pedido:
            # Verifica se o periodo está ativo
            periodo = Periodo.query.get(periodo_id)
            if not periodo or not periodo.ativo:
                return jsonify({'erro': 'Período fechado'}), 403
                
            pedido = Pedido(
                usuario_id=session['usuario_id'], 
                loja_id=session['loja_id'], 
                periodo_id=periodo_id, 
                status='Aberto'
            )
            db.session.add(pedido)
            db.session.flush() # Garante o ID

        # 2. Salva ou Remove o Item
        item = ItemPedido.query.filter_by(pedido_id=pedido.id, produto_id=produto_id).first()
        
        if item:
            if quantidade > 0:
                item.quantidade = quantidade
            else:
                db.session.delete(item)
        elif quantidade > 0:
            db.session.add(ItemPedido(pedido_id=pedido.id, produto_id=produto_id, quantidade=quantidade))
        
        # Atualiza hora da alteração
        pedido.data_alteracao = datetime.now()
        db.session.commit()
        
        return jsonify({'status': 'salvo', 'hora': datetime.now().strftime('%H:%M:%S')})

    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

@app.route('/admin/salvar_consolidacao', methods=['POST'])
def salvar_consolidacao():
    data = request.json
    periodo_id = data.get('periodo_id')
    if not periodo_id: return jsonify({'erro': 'Erro ID'}), 400

    try:
        for item in data.get('produtos', []):
            prod_id = item['produto_id']
            try: desc = float(item['desconto'])
            except: desc = 0.0
            try: bonif = float(item['bonificacao'])
            except: bonif = 0.0
            try: novo_preco = float(item['preco'])
            except: novo_preco = 0.0

            prod = Produto.query.get(prod_id)
            if prod and novo_preco > 0: prod.preco = novo_preco

            negoc = Negociacao.query.filter_by(periodo_id=periodo_id, produto_id=prod_id).first()
            if not negoc:
                negoc = Negociacao(periodo_id=periodo_id, produto_id=prod_id)
                db.session.add(negoc)
            negoc.desconto = desc
            negoc.bonificacao = bonif

            for loja_id_str, qtd_val in item.get('qtds', {}).items():
                loja_id = int(loja_id_str)
                try: qtd_nova = int(qtd_val)
                except: qtd_nova = 0
                
                pedido = Pedido.query.filter_by(loja_id=loja_id, periodo_id=periodo_id).first()
                if not pedido and qtd_nova > 0:
                    dono = Usuario.query.filter_by(loja_id=loja_id).first()
                    uid = dono.id if dono else session['usuario_id']
                    pedido = Pedido(usuario_id=uid, loja_id=loja_id, periodo_id=periodo_id, status='Aberto')
                    db.session.add(pedido)
                    db.session.flush()
                
                if pedido:
                    item_ped = ItemPedido.query.filter_by(pedido_id=pedido.id, produto_id=prod_id).first()
                    if item_ped:
                        if qtd_nova > 0: item_ped.quantidade = qtd_nova
                        else: db.session.delete(item_ped)
                    elif qtd_nova > 0:
                        db.session.add(ItemPedido(pedido_id=pedido.id, produto_id=prod_id, quantidade=qtd_nova))

        for obs in data.get('observacoes', []):
            lab = obs['laboratorio']
            loja_id_obs = int(obs['loja_id']) if obs['loja_id'] else None
            texto = obs['texto']
            
            filtro = Observacao.loja_id == loja_id_obs if loja_id_obs else Observacao.loja_id.is_(None)
            reg = Observacao.query.filter(Observacao.periodo_id == periodo_id, Observacao.laboratorio == lab, filtro).first()
            if reg: reg.texto = texto
            elif texto: db.session.add(Observacao(periodo_id=periodo_id, laboratorio=lab, loja_id=loja_id_obs, texto=texto))

        db.session.commit()
        return jsonify({'mensagem': 'Salvo!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500

# --- SETUP ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Loja.query.first():
            l1, l2, l3, l4, l5 = Loja(nome="Campina Grande"), Loja(nome="Maceió"), Loja(nome="Recife"), Loja(nome="Natal"), Loja(nome="Pesqueira")
            db.session.add_all([l1, l2, l3, l4, l5])
            u1 = Usuario(nome="Miguel", email="miguel@loja.com", senha="1234", funcao="Loja", loja=l1, verificado=True)
            u2 = Usuario(nome="Comprador", email="admin@central.com", senha="1234", funcao="Admin", verificado=True)
            db.session.add_all([u1, u2])
            db.session.commit()

        prods_2_1 = [("Cevamec 1% 50ml", "CEVA BOVINO", 12), ("Mogidex 100ml", "OUROFINO", 12)]
        for n, l, c in prods_2_1:
            if not Produto.query.filter_by(nome=n).first(): db.session.add(Produto(nome=n, laboratorio=l, unidade_caixa=c, grupo='2.1'))
        
        prods_2_2 = [("Adethor 250ml", "FABIANI", 4), ("Ferrodex B12 50ml", "FABIANI", 4)]
        for n, l, c in prods_2_2:
            if not Produto.query.filter_by(nome=n).first(): db.session.add(Produto(nome=n, laboratorio=l, unidade_caixa=c, grupo='2.2'))
        
        if not Produto.query.filter_by(nome="Papel A4").first(): db.session.add(Produto(nome="Papel A4", laboratorio="SUPRIMENTOS", unidade_caixa=10, grupo='DIVERSOS'))
        db.session.commit()
    
    app.run(debug=True)