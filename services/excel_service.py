"""
services/excel_service.py
Responsável por toda geração de planilhas Excel do sistema.
Extraído de app.py para separar lógica de negócio das rotas Flask.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Ordem fixa das lojas nas colunas do Excel
ORDEM_LOJAS = ["Pesqueira", "Recife", "Campina Grande", "Natal", "Maceió"]

# Apelido exibido no cabeçalho (Recife aparece como "Cruza")
APELIDO_LOJA = {"Recife": "Cruza"}

# Estilos reutilizáveis
_BROWN  = PatternFill(start_color="8B4513", end_color="8B4513", fill_type="solid")
_RED    = PatternFill(start_color="B71C1C", end_color="B71C1C", fill_type="solid")
_GRAY   = PatternFill(start_color="444444", end_color="444444", fill_type="solid")
_DARK   = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
_WHITE  = Font(color="FFFFFF", bold=True)
_BOLD   = Font(bold=True)
_CENTER = Alignment(horizontal="center", vertical="center")
_BORDER = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'),  bottom=Side(style='thin')
)


def _nome_col(loja):
    """Retorna o nome a exibir no cabeçalho — aplica apelidos."""
    return APELIDO_LOJA.get(loja.nome, loja.nome)


def ordenar_lojas(lojas):
    """Ordena uma lista de objetos Loja pela ordem personalizada."""
    return sorted(lojas, key=lambda l: ORDEM_LOJAS.index(l.nome) if l.nome in ORDEM_LOJAS else 999)


def gerar_excel_unico(periodo, laboratorio_nome, lojas_filtradas, db, Produto, ItemPedido, Pedido):
    """
    Gera um Excel com os pedidos de UM laboratório para envio por e-mail.
    Retorna um objeto BytesIO pronto para anexar.

    Parâmetros:
        periodo          — objeto Periodo do banco
        laboratorio_nome — string com o nome do laboratório
        lojas_filtradas  — lista de objetos Loja já filtrada pelo usuário
        db               — instância do SQLAlchemy
        Produto          — model Produto (injetado para evitar import circular)
        ItemPedido       — model ItemPedido
        Pedido           — model Pedido
    """

    lojas = ordenar_lojas(lojas_filtradas)

    wb = Workbook()
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    ws = wb.create_sheet(title=laboratorio_nome[:30])

    # Cabeçalho linha 1
    for col, (valor, fill) in enumerate([
        ("PRODUTO", _BROWN), ("CX EMB", _BROWN)
    ], start=1):
        c = ws.cell(row=1, column=col, value=valor)
        c.font = _WHITE; c.fill = fill; c.alignment = _CENTER; c.border = _BORDER

    col = 3
    for loja in lojas:
        c = ws.cell(row=1, column=col, value=_nome_col(loja))
        c.font = _WHITE; c.fill = _BROWN; c.alignment = _CENTER
        col += 1

    ws.cell(row=1, column=col, value="TOTAL").font = _WHITE
    ws.cell(row=1, column=col).fill = _BROWN

    # Dados
    row = 2
    produtos = Produto.query.filter_by(
        grupo=periodo.grupo_filtro,
        laboratorio=laboratorio_nome
    ).order_by(Produto.nome).all()

    for p in produtos:
        ws.cell(row=row, column=1, value=p.nome).border = _BORDER
        ws.cell(row=row, column=2, value=p.unidade_caixa).alignment = _CENTER
        ws.cell(row=row, column=2).border = _BORDER

        col = 3
        total_linha = 0
        for loja in lojas:
            qtd = db.session.query(
                db.func.sum(ItemPedido.quantidade)
            ).join(Pedido).filter(
                ItemPedido.produto_id == p.id,
                Pedido.loja_id == loja.id,
                Pedido.periodo_id == periodo.id
            ).scalar() or 0

            c = ws.cell(row=row, column=col, value=qtd)
            c.alignment = _CENTER; c.border = _BORDER
            if qtd == 0:
                c.font = Font(color="CCCCCC")
            total_linha += qtd
            col += 1

        c = ws.cell(row=row, column=col, value=total_linha)
        c.font = _BOLD; c.alignment = _CENTER; c.border = _BORDER
        row += 1

    ws.column_dimensions['A'].width = 30

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def gerar_excel_consolidado(periodo, lojas, dados_lab):
    """
    Gera o Excel completo de consolidação (todas as abas / todos os laboratórios).
    Retorna um BytesIO pronto para download.

    Parâmetros:
        periodo    — objeto Periodo
        lojas      — lista ordenada de objetos Loja
        dados_lab  — dict {laboratorio: [lista de itens com qtds, preco, desconto, etc.]}
    """
    lojas = ordenar_lojas(lojas)

    wb = Workbook()
    if 'Sheet' in wb.sheetnames:
        wb.remove(wb['Sheet'])

    for lab_nome, itens in dados_lab.items():
        ws = wb.create_sheet(title=lab_nome[:30])

        # Linha 1 — cabeçalhos principais
        ws.merge_cells('A1:A2')
        _cell(ws, 'A1', "PRODUTO", _BROWN)

        ws.merge_cells('B1:B2')
        _cell(ws, 'B1', "CX EMB", _BROWN)

        col_ini = 3
        col_fim = col_ini + len(lojas) - 1
        ws.merge_cells(start_row=1, start_column=col_ini, end_row=1, end_column=col_fim)
        c = ws.cell(row=1, column=col_ini, value="QUANTIDADES POR LOJA")
        c.fill = _BROWN; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER

        col_total = col_fim + 1
        ws.merge_cells(start_row=1, start_column=col_total, end_row=2, end_column=col_total)
        c = ws.cell(row=1, column=col_total, value="TOTAL")
        c.fill = _RED; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER

        col_preco = col_total + 1
        ws.merge_cells(start_row=1, start_column=col_preco, end_row=2, end_column=col_preco)
        c = ws.cell(row=1, column=col_preco, value="PREÇO TAB")
        c.fill = _GRAY; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER

        col_negoc = col_preco + 1
        ws.merge_cells(start_row=1, start_column=col_negoc, end_row=1, end_column=col_negoc + 2)
        c = ws.cell(row=1, column=col_negoc, value="NEGOCIAÇÃO")
        c.fill = _DARK; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER

        # Linha 2 — nomes das lojas e sub-cabeçalhos de negociação
        cur = col_ini
        for loja in lojas:
            c = ws.cell(row=2, column=cur, value=_nome_col(loja))
            c.fill = _BROWN; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER
            cur += 1

        for i, h in enumerate(["DESC %", "VALOR FECHADO", "BONIF %"]):
            c = ws.cell(row=2, column=col_negoc + i, value=h)
            c.fill = _DARK; c.font = _WHITE; c.alignment = _CENTER; c.border = _BORDER

        # Dados
        row_num = 3
        for item in itens:
            ws.cell(row=row_num, column=1, value=item['nome']).border = _BORDER
            ws.cell(row=row_num, column=2, value=item['caixa']).alignment = _CENTER

            cur = col_ini
            for loja in lojas:
                qtd = item['qtds'].get(loja.id, 0)
                c = ws.cell(row=row_num, column=cur, value=qtd)
                c.alignment = _CENTER; c.border = _BORDER
                cur += 1

            c = ws.cell(row=row_num, column=col_total, value=item['total'])
            c.font = _BOLD; c.alignment = _CENTER; c.border = _BORDER

            c = ws.cell(row=row_num, column=col_preco, value=item['preco'])
            c.number_format = '#,##0.00'; c.border = _BORDER

            desc = item.get('desconto', 0)
            c = ws.cell(row=row_num, column=col_negoc, value=desc)
            c.alignment = _CENTER; c.border = _BORDER; c.font = Font(color="0000FF", bold=True)

            preco_final = item['preco'] - (item['preco'] * (desc / 100))
            c = ws.cell(row=row_num, column=col_negoc + 1, value=preco_final)
            c.number_format = '#,##0.00'; c.font = Font(color="006400", bold=True); c.border = _BORDER

            c = ws.cell(row=row_num, column=col_negoc + 2, value=item.get('bonificacao', 0))
            c.alignment = _CENTER; c.border = _BORDER

            row_num += 1

        ws.column_dimensions['A'].width = 30
        for col in range(2, 20):
            try:
                ws.column_dimensions[chr(64 + col)].width = 12
            except Exception:
                pass

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _cell(ws, coord, value, fill):
    """Atalho para formatar célula de cabeçalho."""
    c = ws[coord]
    c.value = value
    c.fill = fill
    c.font = _WHITE
    c.alignment = _CENTER
    c.border = _BORDER
    return c