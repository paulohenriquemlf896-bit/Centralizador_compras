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
    funcao = db.Column(db.String(20), nullable=False) # 'Loja' ou 'Admin'
    loja_id = db.Column(db.Integer, db.ForeignKey('loja.id'), nullable=True)
    loja = db.relationship('Loja', backref=db.backref('usuarios', lazy=True))

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    laboratorio = db.Column(db.String(100), nullable=False) # Ex: CEVA BOVINO
    unidade_caixa = db.Column(db.Integer, default=1) # Qtd na caixa de embarque (padrão 1)

# --- ROTAS (PÁGINAS) ---

@app.route('/')
def index():
    if 'usuario_id' in session:
        if session.get('funcao') == 'Admin':
            return redirect(url_for('dashboard_admin'))
        else:
            return redirect(url_for('dashboard_loja'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        user = Usuario.query.filter_by(email=email).first()
        
        if user and user.senha == senha:
            session['usuario_id'] = user.id
            session['nome'] = user.nome
            session['funcao'] = user.funcao
            
            if user.funcao == 'Admin':
                return redirect(url_for('dashboard_admin'))
            else:
                return redirect(url_for('dashboard_loja'))
        else:
            erro = 'Email ou senha incorretos.'
    return render_template('login.html', erro=erro)

@app.route('/dashboard/loja')
def dashboard_loja():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard_loja.html', nome=session['nome'])

@app.route('/pedido/medicamentos')
def pedido_medicamentos():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    # Busca apenas os produtos que são do laboratório CEVA BOVINO
    # No futuro, você pode buscar de vários laboratórios de uma vez
    produtos_ceva = Produto.query.filter_by(laboratorio="CEVA BOVINO").order_by(Produto.nome).all()
    
    return render_template('pedido_form.html', produtos=produtos_ceva, nome_periodo="Medicamentos 2.1")

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard_admin.html', nome=session['nome'])

@app.route('/admin/consolidacao')
def consolidacao_pedidos():
    if 'usuario_id' not in session or session.get('funcao') != 'Admin':
        return redirect(url_for('login'))
    
    # Busca TUDO (ordenado por laboratório para facilitar)
    produtos = Produto.query.order_by(Produto.laboratorio, Produto.nome).all()
    
    # Dicionário para agrupar: {'CEVA BOVINO': [...], 'OUTRO LAB': [...]}
    dados_agrupados = {}
    
    # --- SIMULAÇÃO DE DADOS ---
    import random
    
    # Se quiser ver a segunda aba funcionando, vamos fingir que tem outro lab
    # (Se você já tiver outros labs no banco, pode apagar essa linha abaixo)
    if not Produto.query.filter_by(laboratorio="ZOETIS (TESTE)").first():
        produtos.append(Produto(nome="CDECTIN 500ML", laboratorio="ZOETIS (TESTE)", unidade_caixa=12))

    for p in produtos:
        # Cria a lista do laboratório se ainda não existir no dicionário
        if p.laboratorio not in dados_agrupados:
            dados_agrupados[p.laboratorio] = []

        # Simula os pedidos
        qtd_campina = p.unidade_caixa * random.choice([0, 1, 2])
        qtd_maceio = p.unidade_caixa * random.choice([0, 1])
        qtd_recife = p.unidade_caixa * random.choice([0, 1, 3])
        qtd_natal = p.unidade_caixa * random.choice([0, 1])
        qtd_pesqueira = 0
        
        total = qtd_campina + qtd_maceio + qtd_recife + qtd_natal + qtd_pesqueira
        
        # Adiciona o item na lista do laboratório correto
        dados_agrupados[p.laboratorio].append({
            'nome': p.nome,
            'caixa': p.unidade_caixa,
            'campina': qtd_campina,
            'maceio': qtd_maceio,
            'recife': qtd_recife,
            'natal': qtd_natal,
            'pesqueira': qtd_pesqueira,
            'total': total
        })
        
    return render_template('consolidacao.html', dados=dados_agrupados, data_hoje=datetime.now().strftime('%d/%m/%Y'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DADOS INICIAIS (CEVA BOVINO) ---
lista_ceva_bovino = [
    "ADE INJ 100ML BR", "ADE INJ 200ML BR", "ADE INJ 50ML BR", "AMOCLOX CX 30 X 7 GR",
    "ANASEDAN DP 24x10ML", "ANAVAC B19 10D BR", "ANAVAC B19 15D BR", "BENZOATO HC 50ML BR",
    "CEFAVET 30 X 10 ML BR", "CEVARELIN 50 ML", "CIPIONATO 50 ML", "COMBO POUR ON 1L (NEW)",
    "COMBO POUR ON 5L BR", "COMBO POUR ON 5L S/ APL. BR", "CYPERCLOR PLUS PULV CX 6 X 1 LT",
    "DEXACORT INJ. 25MG 10ML BR", "DEXACORT INJ. 25MG 50ML BR", "DOPALEN PEC 24X10ML",
    "Eprecis INJ 500 ML", "EPRECIS INJ 50ML", "FIPROLINE DUO 1L BR", "FIPROLINE DUO 1L SEM APLIC BR",
    "FIPROLINE DUO 250ML BR", "FIPROLINE DUO 5L BR", "FLURON GOLD CX 6X1L", "FLURON GOLD CX 6X2L",
    "FOLIC-REC LIQUIDO 30 ML", "INDIGEST 30ML", "KETOFEN INJ 10% 50ML BR", "KIT APLICADOR FIPROLINE DUO",
    "LUTEGLAN 20ML BR", "MARBOX 100ML CLAS BR", "NIGLUMINE 100ML BR", "NIGLUMINE 50ML BR",
    "PARTOMICINA 12X20ML BR", "PPD TUBERCULINA 2ML", "PPD TUBERCULINA 5ML", "PRO-CICLAR 10X10 BR",
    "Pro-ciclar 10x10 S/ Aplicador", "PURITEC GOLD INJ 6x1000ML", "PURITEC GOLD INJ 6x500ML",
    "RABMUNE 25D BR", "RETARDOESTEROIDE 50ML BR", "ROBOFORTE INJ 1L BR", "ROBOFORTE INJ 250ML BR",
    "ROBOFORTE INJ 500ML BR", "TICSON 3,5% 1L BR", "TICSON 3.5% 500ML BR", "TILMICOVET 100ML BR",
    "TYLADEN INJETAVEL CX 12 X 100 ML", "TYLADEN INJETAVEL CX 12 X 50 ML", "VELACTIS 5ML",
    "VIVEDIUM 4G + DILUENTE 200 ML BR", "ZELERIS 100ML CLAS BR", "MODIFIC 500ML"
]

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # 1. Cria Lojas e Usuarios se não existirem
        if not Loja.query.first():
            print("Criando lojas e usuários padrão...")
            loja1 = Loja(nome="Campina Grande")
            loja2 = Loja(nome="Maceió")
            db.session.add_all([loja1, loja2])
            
            user_loja = Usuario(nome="Miguel", email="miguel@loja.com", senha="1234", funcao="Loja", loja=loja1)
            user_admin = Usuario(nome="Comprador", email="admin@central.com", senha="1234", funcao="Admin")
            db.session.add_all([user_loja, user_admin])
            db.session.commit()

        # 2. Cadastra produtos da CEVA BOVINO se não existirem
        print("Verificando produtos CEVA BOVINO...")
        contador_novos = 0
        for nome_prod in lista_ceva_bovino:
            # Verifica se já existe esse produto no banco para não duplicar
            existe = Produto.query.filter_by(nome=nome_prod).first()
            if not existe:
                # Como não tenho a info da caixa (ex: 12 ou 24), deixei padrão 1
                # Você poderá editar isso depois no banco
                novo_prod = Produto(nome=nome_prod, laboratorio="CEVA BOVINO", unidade_caixa=1)
                db.session.add(novo_prod)
                contador_novos += 1
        
        if contador_novos > 0:
            db.session.commit()
            print(f"{contador_novos} novos produtos CEVA adicionados com sucesso!")
        else:
            print("Produtos CEVA já estão cadastrados.")

    app.run(debug=True)