"""
services/email_service.py
Responsável pelo envio de e-mails SMTP do sistema.
Extraído de app.py para separar lógica de negócio das rotas Flask.
"""
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def enviar_email_pedido(
    remetente_email: str,
    remetente_senha: str,
    smtp_server: str,
    smtp_port: int,
    destinatario: str,
    lista_cc: list,
    assunto: str,
    corpo: str,
    anexo_bytes,
    nome_anexo: str,
    intervalo_segundos: int = 10
) -> None:
    """
    Envia um e-mail com anexo Excel via SMTP.

    Parâmetros:
        remetente_email    — e-mail do remetente (admin)
        remetente_senha    — senha SMTP (já descriptografada)
        smtp_server        — servidor SMTP (ex: email-ssl.com.br)
        smtp_port          — porta SMTP (465 = SSL, 587 = TLS)
        destinatario       — e-mail do fornecedor
        lista_cc           — lista de e-mails em cópia
        assunto            — assunto do e-mail
        corpo              — texto do corpo
        anexo_bytes        — BytesIO com o Excel gerado
        nome_anexo         — nome do arquivo .xlsx
        intervalo_segundos — pausa entre envios para não ser bloqueado pelo SMTP

    Lança:
        Exception — qualquer erro de conexão ou autenticação SMTP
    """
    msg = MIMEMultipart()
    msg['From']    = remetente_email
    msg['To']      = destinatario
    msg['Cc']      = ", ".join(lista_cc)
    msg['Subject'] = assunto

    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    part = MIMEBase('application', 'octet-stream')
    anexo_bytes.seek(0)
    part.set_payload(anexo_bytes.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{nome_anexo}"')
    msg.attach(part)

    # Escolhe SSL ou STARTTLS conforme a porta
    if int(smtp_port) == 465:
        server = smtplib.SMTP_SSL(smtp_server, int(smtp_port))
    else:
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()

    try:
        server.login(remetente_email, remetente_senha)
        destinatarios_reais = [destinatario] + lista_cc
        server.sendmail(remetente_email, destinatarios_reais, msg.as_string())
    finally:
        server.quit()

    # Pausa para não ser bloqueado por anti-spam
    if intervalo_segundos > 0:
        time.sleep(intervalo_segundos)


def montar_corpo_pedido(lab_nome: str, periodo_nome: str) -> str:
    """Retorna o corpo padrão do e-mail de pedido."""
    return (
        f"Olá,\n\n"
        f"Segue em anexo o arquivo de pedido de compras.\n\n"
        f"Fornecedor: {lab_nome}\n"
        f"Período: {periodo_nome}\n\n"
        f"Este e-mail contém cópia para conferência das filiais.\n\n"
        f"Atenciosamente,\n"
        f"Central de Compras."
    )
