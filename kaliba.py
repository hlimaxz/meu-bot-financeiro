import os
import json
import sqlite3
import threading
import time
import requests
import base64
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq

app = Flask(__name__)
CORS(app)

# Configuração da IA
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    print("⚠️ A variável GROQ_API_KEY não foi configurada.")

client = Groq(api_key=api_key)

def obter_imagem_base64(url_ou_base64):
    """Baixa a imagem com autenticação da Twilio ou aceita a do site."""
    if not url_ou_base64:
        return None
        
    # Se a imagem vier do Site (já vem em formato base64)
    if url_ou_base64.startswith("data:image"):
        return url_ou_base64

    # Se a imagem vier do WhatsApp (URL da Twilio)
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not sid or not token:
        raise Exception("Faltam as credenciais da Twilio no Render.")

    try:
        # Baixa a imagem forçando autenticação
        res = requests.get(url_ou_base64, auth=(sid, token))
        if res.status_code == 200:
            content_type = res.headers.get("Content-Type", "image/jpeg")
            b64_data = base64.b64encode(res.content).decode("utf-8")
            return f"data:{content_type};base64,{b64_data}"
        else:
            raise Exception(f"A Twilio bloqueou o acesso. Código: {res.status_code}")
    except Exception as e:
        raise Exception(f"Falha ao baixar imagem: {e}")

def extrair_dados_da_mensagem(mensagem_usuario, historico_conversa, url_imagem=None):
    prompt_sistema = f"""O SEU NOME é Kaliba. Você é uma assistente financeira pessoal brilhante.
    O nome do usuário é Hector. Hoje é {datetime.now().strftime('%d/%m/%Y')}.
    
    Você DEVE retornar APENAS um objeto JSON válido. Não adicione nenhum texto antes ou depois.
    Formato OBRIGATÓRIO:
    {{
        "intencao": "transacao" ou "conversa",
        "resposta_ia": "Sua resposta humana aqui.",
        "transacoes": []
    }}
    """
    
    if url_imagem:
        # --- FLUXO COM IMAGEM (Usa modelo Llama Vision) ---
        try:
            imagem_b64 = obter_imagem_base64(url_imagem)
        except Exception as e:
            return f"ERRO_TECNICO: {str(e)}"
            
        texto_prompt = mensagem_usuario if mensagem_usuario and mensagem_usuario.strip() else "Analise esta imagem financeira e extraia as informações."
        
        conteudo_usuario = [
            {"type": "text", "text": f"{texto_prompt}\nResponda APENAS com o JSON solicitado."},
            {"type": "image_url", "image_url": {"url": imagem_b64}}
        ]
        
        mensagens_para_ia = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": conteudo_usuario}
        ]
        
        modelo = "llama-3.2-90b-vision-preview" # Único modelo da Groq que lê imagem bem
        usar_json_mode = False # Modelos Vision da Groq não aceitam modo JSON forçado
        
    else:
        # --- FLUXO APENAS TEXTO ---
        mensagens_para_ia = [{"role": "system", "content": prompt_sistema}]
        mensagens_para_ia.extend(historico_conversa)
        mensagens_para_ia.append({"role": "user", "content": mensagem_usuario})
        
        modelo = "llama-3.3-70b-versatile"
        usar_json_mode = True

    try:
        kwargs = {
            "model": modelo,
            "messages": mensagens_para_ia
        }
        if usar_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            
        response = client.chat.completions.create(**kwargs)
        conteudo_resposta = response.choices[0].message.content.strip()
        
        # Como o modelo de visão não aceita JSON mode, limpamos o texto para forçar extrair o JSON
        if not usar_json_mode:
            match = re.search(r'\{.*\}', conteudo_resposta, re.DOTALL)
            if match:
                conteudo_resposta = match.group(0)
                
        return json.loads(conteudo_resposta)
    except Exception as e:
        return f"ERRO_TECNICO: Falha na IA - {str(e)}"


# ==========================================
# ROTAS DO FLASK
# ==========================================

@app.route("/api/chat", methods=["POST"])
def api_chat():
    dados = request.get_json() or {}
    mensagem_usuario = dados.get("message", "")
    url_imagem = dados.get("image", None)

    if not mensagem_usuario and not url_imagem:
        return jsonify({"error": "Mensagem vazia"}), 400

    historico = [] # Simplificado para o front-end
    resultado = extrair_dados_da_mensagem(mensagem_usuario, historico, url_imagem=url_imagem)

    if isinstance(resultado, str) and resultado.startswith("ERRO_TECNICO:"):
        return jsonify({"reply": f"Ops, erro técnico: {resultado}"}), 500

    resposta_texto = resultado.get("resposta_ia", "Não consegui entender, pode repetir?")
    return jsonify({"reply": resposta_texto}), 200

@app.route("/whatsapp", methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'GET':
        return "Endpoint /whatsapp ativo!", 200

    mensagem_usuario = request.values.get('Body', '').strip()
    num_media = int(request.values.get("NumMedia", 0))
    url_imagem = request.values.get("MediaUrl0") if num_media > 0 else None

    resp = MessagingResponse()
    
    # Historico em branco apenas para não quebrar a lógica sem o DB
    historico = [] 
    
    dados = extrair_dados_da_mensagem(mensagem_usuario, historico, url_imagem=url_imagem)

    if isinstance(dados, str) and dados.startswith("ERRO_TECNICO:"):
        resp.message(f"🕵️ Kaliba: Tive um problema: {dados}")
        return str(resp)

    try:
        resposta_da_ia = dados.get("resposta_ia", "Estou processando...")
        resp.message(f"🤖 {resposta_da_ia}")
            
    except Exception as e:
        resp.message(f"❌ Erro: {e}")

    return str(resp)

@app.route("/")
def home():
    return "<h1>🤖 Kaliba ONLINE</h1>", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)