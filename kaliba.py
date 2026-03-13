import os
import json
import sqlite3
import threading
import time
import requests
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = Flask(__name__)

# 1. Configuração da IA
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise ValueError("⚠️ A variável GROQ_API_KEY não foi configurada no Render.")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

# ==========================================
# MOTOR DE KEEP-ALIVE
# ==========================================
URL_DO_BOT = "https://meu-bot-financeiro-vcou.onrender.com/ping"

@app.route("/ping")
def ping():
    return "Bot acordado e operando!", 200

def ping_automatico():
    while True:
        time.sleep(600)
        try:
            requests.get(URL_DO_BOT)
        except Exception as e:
            pass

threading.Thread(target=ping_automatico, daemon=True).start()
# ==========================================

# 2. Banco de Dados
def conectar_banco():
    conn = sqlite3.connect('gastos_kaliba.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            categoria TEXT,
            valor REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    return conn

# Funções de Memória (AGORA COM MEMÓRIA LONGA)
def obter_historico(cursor):
    # Aumentamos para 20 mensagens de histórico para ela não perder o fio da meada!
    cursor.execute("SELECT role, content FROM historico ORDER BY id DESC LIMIT 20")
    linhas = cursor.fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(linhas)]

def salvar_historico(cursor, conn, role, content):
    cursor.execute("INSERT INTO historico (role, content) VALUES (?, ?)", (role, content))
    conn.commit()

# 3. Inteligência Artificial (MODELO 70B - ALTA INTELIGÊNCIA)
def extrair_dados_da_mensagem(mensagem_usuario, historico_conversa):
    meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
    mes_atual_nome = meses_pt[datetime.now().strftime("%m")]
    ano_atual = datetime.now().strftime("%Y")
    
    prompt_sistema = f"""O SEU NOME é Kaliba. Você é uma assistente financeira pessoal brilhante em formato de IA.
    O nome do usuário com quem você conversa é Hector.
    Hoje é {datetime.now().strftime('%d/%m/%Y')} (Mês de {mes_atual_nome} de {ano_atual}).
    
    Sua personalidade: Empática, extremamente lógica, analítica e focada em resolver os problemas do Hector.
    
    REGRAS DE OURO PARA LÓGICA E MEMÓRIA:
    1. Leia TODO o histórico da conversa com atenção. Lembre-se dos valores exatos que o Hector te falou antes.
    2. Se o Hector mudar um valor ou te corrigir (ex: "na verdade vou receber 365"), VOCÊ DEVE DESCARTAR O VALOR ANTIGO e refazer a lógica usando a nova informação imediatamente. Assuma o erro com naturalidade.
    3. Pense passo a passo. Seja clara em como chegou no resultado de um cálculo.
    
    Você DEVE retornar APENAS um objeto JSON válido, com esta estrutura exata:
    {{
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta humana, natural e muito inteligente.",
        "transacoes": [
            {{"categoria": "Nome Curto", "valor": 0.0, "tipo": "gasto" ou "ganho"}}
        ]
    }}
    
    Regras para o JSON:
    1. Se ele estiver apenas conversando ou pedindo cálculos, a intenção é "conversa" e "transacoes" fica vazia [].
    2. Apenas preencha "transacoes" se ele afirmar que FEZ um gasto ou RECEBEU dinheiro para registrar na planilha hoje.
    """
    
    mensagens_para_ia = [{"role": "system", "content": prompt_sistema}]
    mensagens_para_ia.extend(historico_conversa)
    mensagens_para_ia.append({"role": "user", "content": f"Mensagem do Hector: '{mensagem_usuario}'"})
    
    try:
        # AQUI ESTÁ O UPGRADE DE INTELIGÊNCIA! Trocamos para o modelo 70B!
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_format={ "type": "json_object" },
            messages=mensagens_para_ia
        )
        return json.loads(response.choices[0].message.content)
        
    except Exception as e:
        return f"ERRO_TECNICO: {str(e)}"

# 4. Conexão com WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    mensagem_usuario = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    conn = conectar_banco()
    cursor = conn.cursor()

    if "limpar tudo" in mensagem_usuario or "resetar" in mensagem_usuario or "limpar chat" in mensagem_usuario:
        cursor.execute("DELETE FROM gastos")
        cursor.execute("DELETE FROM historico")
        conn.commit()
        conn.close()
        resp.message("✅ Suas contas e minha memória foram zeradas com sucesso!")
        return str(resp)

    historico = obter_historico(cursor)
    dados = extrair_dados_da_mensagem(mensagem_usuario, historico)

    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Ops, o motor travou:\n\n{dados}")
        conn.close()
        return str(resp)

    try:
        intencao = dados.get("intencao", "conversa")
        resposta_da_ia = dados.get("resposta_ia", "")
        transacoes = dados.get("transacoes", [])
        
        salvar_historico(cursor, conn, "user", mensagem_usuario)
        salvar_historico(cursor, conn, "assistant", resposta_da_ia)
        
        if intencao == "conversa" or not transacoes:
            resp.message(f"🤖 {resposta_da_ia}")
            
        else:
            data_atual = datetime.now().strftime("%Y-%m-%d")
            
            for item in transacoes:
                categoria = str(item.get('categoria', 'Geral')).capitalize()
                valor_str = str(item.get('valor', 0)).replace(",", ".")
                valor_absoluto = abs(float(valor_str))
                tipo = str(item.get('tipo', 'gasto')).lower()
                
                if tipo == 'ganho' or tipo == 'receita':
                    valor_banco = -valor_absoluto
                else:
                    valor_banco = valor_absoluto
                    
                cursor.execute('INSERT INTO gastos (data, categoria, valor) VALUES (?, ?, ?)', (data_atual, categoria, valor_banco))
            
            conn.commit()
            
            mes_atual = datetime.now().strftime("%Y-%m")
            cursor.execute('SELECT categoria, valor FROM gastos WHERE data LIKE ?', (f'{mes_atual}%',))
            registros = cursor.fetchall()
            
            meses_pt = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril", "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto", "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}
            nome_mes = meses_pt[datetime.now().strftime("%m")]
            
            extrato_txt = f"🗓️ Agenda Mês: {nome_mes}\n✅ Movimentações:\n"
            total = 0.0
            
            for cat, val in registros:
                total += val
                cat_formatada = cat.lower()
                val_formatado = f"{abs(val):.2f}".replace(".", ",")
                
                if val < 0:
                    extrato_txt += f"🟢 + {cat_formatada}: R$ {val_formatado}\n"
                else:
                    extrato_txt += f"🔴 - {cat_formatada}: R$ {val_formatado}\n"
            
            total_formatado = f"{total:.2f}".replace(".", ",")
            
            if total > 0:
                extrato_txt += f"\n📊 Saldo Atual = 🔴 R$ -{total_formatado} (Gastando mais do que ganha)"
            else:
                extrato_txt += f"\n📊 Saldo Atual = 🟢 R$ {str(total_formatado).replace('-', '')} (No azul!)"
            
            mensagem_final = f"🤖 {resposta_da_ia}\n\n{extrato_txt}"
            resp.message(mensagem_final)
            
    except Exception as e:
        resp.message(f"Erro interno ao processar os dados: {e}")

    conn.close()
    return str(resp)

if __name__ == "__main__":
    # O Render passa a porta correta na variável de ambiente PORT
    # Se não encontrar, ele usa a 5000 como reserva.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)