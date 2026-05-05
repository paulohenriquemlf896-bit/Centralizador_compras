import sqlite3
import pandas as pd
import os

# 1. Procura o banco de dados na pasta 'instance' primeiro (padrão do Flask)
if os.path.exists("instance/banco_dados.db"):
    caminho_banco = "instance/banco_dados.db"
elif os.path.exists("banco_dados.db"):
    caminho_banco = "banco_dados.db"
else:
    print("ERRO: Nenhum banco de dados encontrado!")
    exit()

print(f"-> Lendo o banco de dados em: {caminho_banco}")

# 2. Conecta e puxa os dados
con = sqlite3.connect(caminho_banco)
df = pd.read_sql_query("SELECT * FROM produto", con)
con.close()

# 3. Mostra o que encontrou no terminal para você ter certeza
fornecedores = df['laboratorio'].dropna().unique()
print(f"-> Foram encontrados {len(df)} produtos no total.")
print(f"-> Fornecedores encontrados: {list(fornecedores)}")

arquivo_excel = "produtos_por_fornecedor.xlsx"

# 4. Gera o Excel
with pd.ExcelWriter(arquivo_excel, engine='openpyxl') as writer:
    for fornecedor in fornecedores:
        # Filtra os produtos
        df_filtrado = df[df['laboratorio'] == fornecedor]
        
        # Limpa o nome para o Excel não dar erro (máx 31 caracteres, sem barras)
        nome_aba = str(fornecedor)[:31].replace('/', '-').replace('\\', '-')
        
        # Salva na aba
        df_filtrado.to_excel(writer, sheet_name=nome_aba, index=False)

print(f'\n[OK] Arquivo "{arquivo_excel}" gerado com sucesso! Verifique as abas na parte inferior do Excel.')