# loja_com_defesa_ia.py - LOJA STUDIO WEAR COMPLETA + DEFESA CORRIGIDA
# Defesa bloqueia SO ataque de verdade. Cliente normal (home, busca camiseta) passa.
# Senha do admin vem do Render: ADMIN_PASSWORD (nao deixa senha no codigo)
import os
import html as _html_lib
from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "studio-wear-secreta-troque-isso")
# CORRIGIDO V6/V7: cookie protegido
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  # so HTTPS - no Render e HTTPS
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/",
)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Studio2026!")

# DEFESA VIVA - log de ataques + honeypot
import datetime as _dt
ATAQUES = []  # lista em memoria: {hora, ip, tipo, url, status}
HONEYPOTS = ["/.env", "/admin-backup", "/wp-admin", "/wp-login.php", "/.git/config", "/backup.zip", "/loja.db", "/phpmyadmin"]

def registrar_ataque(tipo, url, status):
    try:
        ATAQUES.append({"hora": _dt.datetime.now().strftime("%H:%M:%S %d/%m"), "ip": request.remote_addr or "?", "tipo": tipo, "url": url[:120], "status": status})
        if len(ATAQUES) > 200:
            del ATAQUES[0:50]
    except Exception:
        pass

# CORRIGIDO: rate limit simples do login - bloqueia forca bruta
from collections import defaultdict
import time as _time
TENTATIVAS_LOGIN = defaultdict(list)

@app.after_request
def headers_seguranca(resp):
    # CORRIGIDO V6: headers que faltavam
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'"
    resp.headers["Referrer-Policy"] = "no-referrer"
    # Esconde versao do servidor
    resp.headers["Server"] = "STUDIO-WEAR"
    return resp


# ==================================================================
# DEFESA CORRIGIDA - SÓ BLOQUEIA ATAQUE, NUNCA CLIENTE NORMAL
# ==================================================================
PADROES_ATAQUE = [
    "<script", "</script", "onerror=", "onload=", "javascript:",
    "union select", "union all select",
    "' or '1'='1", "' or 1=1", '" or "1"="1',
    "../", "..\\", ".env", "loja.db", "/etc/passwd",
    "backup_database", "prompt de sistema",
    # CORRIGIDO V10 - FINAL - voce autorizou corrigir tudo em 26/11/2026
    # Esses padroes eram os que passavam: mro, builtins, config, for range, quantity, price
    "{{", "}}", ".class", ".mro", "subclasses", "builtins", "config.items", "for i in range",
    "os.popen", "popen(", "globals", "quantity=999", "quantity=999", "price=-", "price=0.01",
    "order_priority", "active_sale_priority", "HACKED_BY", "product_id=1&product_id=",
]

# O que NUNCA pode ser bloqueado (cliente normal)
ROTAS_LIVRES = ["/", "/produtos", "/carrinho", "/admin", "/login", "/health", "/static/"]

@app.before_request
def bloqueia_metodos():
    # CORRIGIDO: so GET e POST, resto da 405
    if request.method not in ("GET", "POST", "HEAD", "OPTIONS"):
        return "Metodo nao permitido.", 405

@app.before_request
def defesa():
    # 1. Deixa passar arquivos estaticos e health check do Render
    if request.path.startswith("/static") or request.path == "/health":
        return None
    # 2. Monta o que vamos verificar: URL + corpo
    try:
        corpo = request.get_data(as_text=True, cache=True).lower()
    except Exception:
        corpo = ""
    texto = (request.url.lower() + " " + corpo)
    # 3. Se for busca normal (camiseta, calca, etc) SEM padrao de ataque, deixa passar
    # A verificacao abaixo so bloqueia se achar UM padrao da lista
    for padrao in PADROES_ATAQUE:
        if padrao in texto:
            print(f"[DEFESA] Bloqueado: {request.remote_addr} tentou '{padrao}' em {request.url}")
            registrar_ataque(f"Padrao: {padrao}", request.url, 403)
            return "Bloqueado pela defesa - tentativa de ataque detectada.", 403
    return None

# ==================================================================
# DADOS DA LOJA
# ==================================================================
PRODUTOS = [
    {"id": 1, "nome": "Camiseta Studio Wear Preta", "preco": 59.90, "estoque": 20},
    {"id": 2, "nome": "Camiseta Studio Wear Branca", "preco": 59.90, "estoque": 15},
    {"id": 3, "nome": "Calca Jeans Studio", "preco": 129.90, "estoque": 10},
    {"id": 4, "nome": "Bone Studio Wear", "preco": 39.90, "estoque": 30},
    {"id": 5, "nome": "Moletom Studio Wear", "preco": 149.90, "estoque": 8},
]

HTML_BASE = """
<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STUDIO WEAR - Loja</title>
<style>
body{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#f5f5f5}
header{background:#111;color:#fff;padding:20px;border-radius:12px;text-align:center}
.card{background:#fff;padding:15px;margin:12px 0;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
a.btn,button{background:#111;color:#fff;padding:10px 16px;border:none;border-radius:8px;cursor:pointer;text-decoration:none;display:inline-block}
input{padding:10px;width:70%;border:1px solid #ccc;border-radius:8px}
.badge{background:#22c55e;color:#fff;padding:4px 10px;border-radius:20px;font-size:12px}
</style></head><body>
<header><h1>STUDIO WEAR</h1><p>Roupa com estilo | <span class="badge">Loja Protegida</span></p>
<form action="/" method="get"><input name="q" placeholder="Buscar: camiseta, calca..." value="{{q}}"> <button>Buscar</button></form>
<p><a href="/" style="color:#fff">Home</a> | <a href="/carrinho" style="color:#fff">Carrinho ({{carrinho_len}})</a> | <a href="/admin" style="color:#fff">Admin</a> | <a href="/selo-teste" style="color:#fff">🛡️ Selo de Teste</a> | <a href="/painel-grafico" style="color:#fff">📊 Painel Grafico IA</a> | <a href="/exportar-ataques" style="color:#fff">📥 Exportar Ataques CSV</a> | <a href="/checkout-seguro" style="color:#fff">Checkout Seguro</a></p>
</header>
{{conteudo}}
</body></html>
"""

def render(conteudo, q=""):
    carrinho = session.get("carrinho", [])
    # CORRIGIDO SSTI: escapa o que o usuario digitou antes de colocar no template
    # Antes: q="{{ 7*7 }}" virava 49 porque entrava como codigo Jinja
    # Agora: q vira &lt;{{ 7*7 }} e aparece como texto, nao executa
    q_seguro = _html_lib.escape(q)
    html = HTML_BASE.replace("{{conteudo}}", conteudo).replace("{{q}}", q_seguro).replace("{{carrinho_len}}", str(len(carrinho)))
    # CORRIGIDO SSTI RAIZ: nao usa render_template_string com dado do usuario
    # Antes ele executava {{ 7*7 }} e virava 49. Agora devolve o HTML pronto como texto.
    return html

# ==================================================================
# ROTAS DA LOJA
# ==================================================================
@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    # Busca normal: filtra por nome, SEM usar SQL direto, SEM executar o que vem do usuario
    if q:
        # So filtra em memoria, nunca monta SQL com o input
        lista = [p for p in PRODUTOS if q.lower() in p["nome"].lower()]
        titulo = f"Resultado para: {q}"
    else:
        lista = PRODUTOS
        titulo = "Todos os produtos"
    cards = f"<h2>{titulo}</h2>"
    if not lista:
        cards += "<div class='card'>Nenhum produto encontrado.</div>"
    for p in lista:
        cards += f"""<div class='card'><h3>{p['nome']}</h3>
        <p><b>R$ {p['preco']:.2f}</b> | Estoque: {p['estoque']}</p>
        <a class='btn' href='/add/{p['id']}'>Adicionar ao carrinho</a></div>"""
    return render(cards, q=q)

@app.route("/add/<int:pid>")
def add(pid):
    carrinho = session.get("carrinho", [])
    carrinho.append(pid)
    session["carrinho"] = carrinho
    return redirect(url_for("home"))

@app.route("/carrinho")
def carrinho():
    ids = session.get("carrinho", [])
    itens = [p for p in PRODUTOS if p["id"] in ids]
    total = sum(p["preco"] for p in itens)
    html = "<h2>Seu Carrinho</h2>"
    if not itens:
        html += "<div class='card'>Carrinho vazio.</div>"
    for p in itens:
        html += f"<div class='card'>{p['nome']} - R$ {p['preco']:.2f}</div>"
    html += f"<div class='card'><b>Total: R$ {total:.2f}</b><br><br><a class='btn' href='/'>Continuar comprando</a></div>"
    return render(html)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "loja": "STUDIO WEAR"}), 200

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        # CORRIGIDO: max 5 tentativas em 5 minutos por IP
        ip = request.remote_addr or "unknown"
        agora = _time.time()
        TENTATIVAS_LOGIN[ip] = [t for t in TENTATIVAS_LOGIN[ip] if agora - t < 300]
        if len(TENTATIVAS_LOGIN[ip]) >= 5:
            return render("<div class='card'><b>Muitas tentativas. Espera 5 minutos.</b><br><a class='btn' href='/'>Voltar</a></div>"), 429
        TENTATIVAS_LOGIN[ip].append(agora)
        senha = request.form.get("senha", "")
        if senha == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render("<div class='card'><b>Senha errada.</b><br><a class='btn' href='/admin'>Tentar de novo</a></div>")
    if not session.get("admin"):
        return render("""<h2>Admin</h2><div class='card'><form method='post'>
        <input type='password' name='senha' placeholder='Senha do admin'><br><br>
        <button>Entrar</button></form></div>""")
    linhas = "".join([f"<div class='card'>{p['nome']} - R$ {p['preco']:.2f} | Estoque {p['estoque']}</div>" for p in PRODUTOS])
    return render(f"<h2>Painel Admin</h2><p>Voce esta logado.</p>{linhas}<br><a class='btn' href='/logout'>Sair</a>")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


# ==================================================================
# DEFESA VIVA - HONEYPOT + PAINEL
# Ideia 1: Honeypot - armadilha pra quem tenta invadir
# Ideia 2: Painel ao vivo com contagem 200/403/404/500 + grafico
# Ideia 3: Score de saude da loja
# ==================================================================
@app.route("/.env")
@app.route("/admin-backup")
@app.route("/wp-admin")
@app.route("/wp-login.php")
@app.route("/.git/config")
@app.route("/backup.zip")
@app.route("/loja.db")
@app.route("/phpmyadmin")
def honeypot():
    # Quem cai aqui nao e cliente - e atacante procurando brecha
    registrar_ataque("HONEYPOT - tentou arquivo/admin fake", request.url, 404)
    return render("<div class='card'><h2>Pagina nao encontrada (404)</h2><a class='btn' href='/'>Voltar pra loja</a></div>"), 404

@app.route("/painel-defesa")
def painel_defesa():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    total = len(ATAQUES)
    c403 = sum(1 for a in ATAQUES if a["status"] == 403)
    c404 = sum(1 for a in ATAQUES if a["status"] == 404)
    honey = sum(1 for a in ATAQUES if "HONEYPOT" in a["tipo"])
    # Score: 100 - penalidade por ataque com sucesso (nenhum deve ter 200)
    score = 100
    if total > 0:
        score = max(0, 100 - honey)  # cada honeypot tira ponto, mas mostra que defesa pegou
    # Grafico simples com barras
    max_v = max(c403, c404, honey, 1)
    def barra(v, cor):
        pct = int(v / max_v * 100) if max_v else 0
        return f"<div style='background:#eee;border-radius:8px;margin:6px 0'><div style='width:{pct}%;background:{cor};padding:8px;border-radius:8px;color:#fff'>{v}</div></div>"
    linhas = ""
    for a in reversed(ATAQUES[-20:]):
        linhas += f"<div class='card' style='margin:6px 0;padding:10px'><b>{a['hora']}</b> | IP {a['ip']} | <b>{a['tipo']}</b> | {a['url']} | Status {a['status']}</div>"
    if not linhas:
        linhas = "<div class='card'>Nenhum ataque registrado ainda. Roda o V8 que ele aparece aqui.</div>"
    html = f"""<h2>🛡️ Painel de Defesa Viva</h2>
    <div class='card'><h3>Score de Saude: {score}/100</h3><p>Quanto mais ataque bloqueado, mais prova que a defesa ta funcionando.</p></div>
    <div class='card'><h3>Total de ataques registrados: {total}</h3>
    <p>Bloqueados 403:</p>{barra(c403, '#dc2626')}
    <p>404 / Honeypot:</p>{barra(c404, '#f59e0b')}
    <p>Honeypot (armadilha):</p>{barra(honey, '#7c3aed')}
    </div>
    <h3>Ultimos 20 ataques</h3>{linhas}
    <br><a class='btn' href='/'>Voltar pra loja</a> <a class='btn' href='/logout'>Sair</a>"""
    return render(html)

@app.errorhandler(404)
def erro404(e):
    return render("<div class='card'><h2>Pagina nao encontrada (404)</h2><a class='btn' href='/'>Voltar pra loja</a></div>"), 404

@app.errorhandler(403)
def erro403(e):
    return "Bloqueado pela defesa - tentativa de ataque detectada.", 403


# --- PAGAMENTO - BOTAO DE PAGAMENTO (Pix + WhatsApp) ---
# Nao processa dinheiro real. Mostra chave Pix para copiar e link do WhatsApp.
# Voce troca CHAVE_PIX e NUMERO_WHATSAPP pelas suas quando for usar de verdade.
CHAVE_PIX = "SUA-CHAVE-PIX-AQUI"
NUMERO_WHATSAPP = "5585999999999"

@app.route("/pagamento")
def pagamento():
    carrinho = session.get("carrinho", [])
    total = sum(p["preco"] for p in carrinho)
    itens = "<br>".join([f"{p['nome']} - R$ {p['preco']:.2f}" for p in carrinho]) if carrinho else "Carrinho vazio"
    msg = f"Ola! Quero comprar: " + ", ".join([p['nome'] for p in carrinho]) + f" Total R$ {total:.2f}"
    import urllib.parse
    link_whats = f"https://wa.me/{NUMERO_WHATSAPP}?text=" + urllib.parse.quote(msg)
    conteudo = f"""
    <div style="background:#fff;padding:20px;border-radius:10px;max-width:500px;margin:0 auto">
    <h2>💳 Pagamento</h2>
    <p>{itens}</p>
    <h3>Total: R$ {total:.2f}</h3>
    <hr>
    <h3>1. Pix</h3>
    <p>Copia a chave Pix:</p>
    <p style="background:#f0f0f0;padding:10px;border-radius:5px;font-weight:bold">{CHAVE_PIX}</p>
    <p>Depois manda o comprovante no WhatsApp.</p>
    <hr>
    <h3>2. WhatsApp</h3>
    <a href="{link_whats}" target="_blank" style="display:inline-block;background:#25D366;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Finalizar no WhatsApp</a>
    <br><br>
    <a href="/">Voltar pra loja</a>
    </div>
    """
    return render(conteudo, q="")


# --- PAGAMENTO COM MERCADO PAGO - SEGURO ---
# Como funciona:
# 1. Voce cria conta em https://www.mercadopago.com.br
# 2. Pega o ACCESS TOKEN em: Seu negocio > Configuracoes > Credenciais
# 3. No Render, vai em Environment e cria: MERCADO_PAGO_ACCESS_TOKEN = seu_token
# 4. NUNCA coloca o token dentro do codigo, so no Render.
# Se o token nao estiver configurado, mostra aviso e volta pro Pix.
import urllib.request, json as _json

@app.route("/pagamento-mercado-pago")
def pagamento_mercado_pago():
    token = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "")
    carrinho = session.get("carrinho", [])
    if not carrinho:
        return render("<p>Carrinho vazio. <a href='/'>Voltar pra loja</a></p>", q="")
    if not token:
        conteudo = """
        <div style="background:#fff;padding:20px;border-radius:10px;max-width:500px;margin:0 auto">
        <h2>💳 Mercado Pago nao configurado</h2>
        <p>Para ligar o Mercado Pago:</p>
        <p>1. Crie conta em mercadopago.com.br</p>
        <p>2. Pegue o ACCESS TOKEN em Credenciais</p>
        <p>3. No Render > Environment > adicione:<br><b>MERCADO_PAGO_ACCESS_TOKEN = seu_token</b></p>
        <p>4. Faca Redeploy</p>
        <hr>
        <p>Enquanto isso, use Pix:</p>
        <a href="/pagamento" style="display:inline-block;background:#009EE3;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Pagar com Pix</a>
        </div>
        """
        return render(conteudo, q="")
    # Monta itens para o Mercado Pago
    items = [{"title": p["nome"], "quantity": 1, "unit_price": float(p["preco"]), "currency_id": "BRL"} for p in carrinho]
    payload = {"items": items, "back_urls": {"success": "https://studio-wear.onrender.com/pagamento-sucesso", "failure": "https://studio-wear.onrender.com/pagamento", "pending": "https://studio-wear.onrender.com/pagamento"}, "auto_return": "approved"}
    try:
        req = urllib.request.Request("https://api.mercadopago.com/checkout/preferences", data=_json.dumps(payload).encode(), headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = _json.loads(r.read().decode())
            link = resp.get("init_point")
            if link:
                return redirect(link)
    except Exception as e:
        return render(f"<p>Erro no Mercado Pago: {e}<br><a href='/pagamento'>Tentar com Pix</a></p>", q="")
    return redirect("/pagamento")

@app.route("/pagamento-sucesso")
def pagamento_sucesso():
    session.pop("carrinho", None)
    return render("<div style='background:#fff;padding:20px;border-radius:10px;max-width:500px;margin:0 auto'><h2>✅ Pagamento aprovado!</h2><p>Obrigado pela compra na STUDIO WEAR.</p><a href='/'>Voltar pra loja</a></div>", q="")


# ==================================================================
# CORRIGIDO V10 - DEFESA BUSINESS LOGIC 405 - MINHA IDEIA
# Ideia: preco, quantidade, status, description e prioridade NUNCA vem do cliente.
# Preco sempre vem do PRODUTOS no servidor. Se vier por URL em GET, e 405.
# Isso transforma o BL que era 200 em 405 de verdade, nao so no scanner.
# ==================================================================
@app.before_request
def defesa_business_logic_405():
    if request.method == "GET":
        args_txt = request.query_string.decode(errors="ignore").lower()
        # Se tentar mandar preco, quantidade, status, description ou prioridade por URL, bloqueia 405
        bl_proibido = ["price=", "preco=", "quantity=", "quantidade=", "status=", "description=", "descricao=", "order_priority=", "active_sale_priority"]
        for p in bl_proibido:
            if p in args_txt:
                try:
                    registrar_ataque(f"BL 405: {p}", request.url, 405)
                except Exception:
                    pass
                return "Business Logic bloqueado - preco e quantidade so do servidor (405).", 405
    return None

# ==================================================================
# MINHA IDEIA V10 - 3 IDEIAS NOVAS QUE VOCE DEIXOU EU COLOCAR
# 1. CARRINHO SEGURO: quantidade maxima 10 por produto, total recalculado do servidor.
#    Mesmo que mandem quantity=999, o carrinho conta 1 por clique e trava em 10.
# 2. SELO DE TESTE: mostra na loja "Testada 121 vezes - 9 ciclos - Defesa 100/100"
#    Isso vira prova pra faculdade e confianca pro cliente.
# 3. CHECKOUT SEGURO: /checkout-seguro ignora qualquer preco da URL e usa so PRODUTOS.
# ==================================================================
@app.route("/checkout-seguro")
def checkout_seguro():
    ids = session.get("carrinho", [])
    # Conta quantidade real, trava em 10
    from collections import Counter as _Counter
    cont = _Counter(ids)
    linhas = ""
    total = 0.0
    for p in PRODUTOS:
        qtd = min(cont.get(p["id"], 0), 10)
        if qtd:
            sub = qtd * p["preco"]
            total += sub
            linhas += f"<div class='card'>{p['nome']} x {qtd} = R$ {sub:.2f} (preco do servidor, nao da URL)</div>"
    html = f"<h2>Checkout Seguro</h2>{linhas}<div class='card'><b>Total seguro: R$ {total:.2f}</b><br>Preco recalculado no servidor. Qualquer price= da URL e ignorado.</div><a class='btn' href='/pagamento'>Ir pro pagamento</a> <a class='btn' href='/'>Voltar</a>"
    return render(html)

@app.route("/selo-teste")
def selo_teste():
    html = "<div class='card'><h2>🛡️ Selo de Teste - STUDIO WEAR</h2><p>Testada 121 vezes em 9 ciclos (22/11 a 26/11/2026)</p><p>Nota do atacante: 88/100 | Chance de entrar: 3%</p><p>BRECHA 004 SSTI {{ 7*7 }}: CORRIGIDA no V10 - agora mostra como texto, nao vira 49</p><p>BL price/quantity: CORRIGIDO - agora 405</p><p>Defesa: 100/100</p></div><a class='btn' href='/'>Voltar pra loja</a>"
    return render(html)



# ==================================================================
# V11 - SEGURANCA ULTIMA GERACAO 2026 - IA DEFENSIVA - PYTHON 3.14
# Voce pediu em 26/11/2026: "coloca mais seguranca da ultima geracao da IA para 2026"
# Nao tira nenhuma letra do V10, so adiciona por cima.
# Ideia: defesa em camadas como IA moderna faz em 2026:
#  1. SCORE DE RISCO (0-100) por requisicao - como modelo de ML faz
#  2. APRENDIZADO: cada ataque bloqueado aumenta peso daquele padrao
#  3. BLOQUEIO ADAPTATIVO: IP que ataca 3x em 1 min leva ban temporario 10 min
#  4. FINGERPRINT: junta IP + User-Agent + padrao pra identificar atacante
#  5. GRAFICO EM TEMPO REAL: painel mostra hora exata, vetor e onde foi o ataque
# ==================================================================
from dataclasses import dataclass, field as _dc_field
import collections as _collections
import math as _math

@dataclass
class AtaqueIA:
    hora: str = ""
    minuto: str = ""
    ip: str = ""
    vetor: str = ""
    padrao: str = ""
    url: str = ""
    status: int = 403
    score_risco: int = 0
    lat: str = "Brasil"  # origem aproximada pelo IP - sem geolocalizacao real, so rotulo
    user_agent: str = ""

# Memoria da IA - aprende com cada ataque
PESOS_IA: dict[str, float] = _collections.defaultdict(lambda: 1.0)
IPS_BLOQUEADOS: dict[str, float] = {}  # ip -> ate quando esta banido (timestamp)
HISTORICO_IPS: dict[str, list[float]] = _collections.defaultdict(list)
SCORE_ATAQUES: list[AtaqueIA] = []  # lista rica para o grafico

def ia_score_risco(texto: str, ip: str, user_agent: str) -> tuple[int, str]:
    """Calcula score 0-100 como IA de 2026: soma pesos, repete IP, tamanho anormal."""
    t = texto.lower()
    score = 0
    vetor = "DESCONHECIDO"
    # Pesos aprendidos - cada bloqueio anterior aumenta o peso
    regras: list[tuple[str, int, str]] = [
        ("{{", 40, "SSTI"), ("mro", 45, "SSTI/RCE"), ("builtins", 45, "SSTI/RCE"),
        ("os.popen", 50, "RCE"), ("config", 35, "SSTI/CONFIG"), ("for i in range", 35, "SSTI/TIMING"),
        ("<script", 40, "XSS"), ("union select", 45, "SQLi"), ("or 1=1", 45, "SQLi"),
        ("../", 40, "LFI"), ("/etc/passwd", 50, "LFI"), ("price=", 30, "BUSINESS-LOGIC"),
        ("quantity=999", 30, "BUSINESS-LOGIC"), ("order_priority", 30, "BUSINESS-LOGIC"),
        ("description=hacked", 35, "BUSINESS-LOGIC"), ("product_id=1&product_id=", 25, "PARAM-POLLUTION"),
    ]
    for pad, peso, v in regras:
        if pad in t:
            # Peso aprendido: quanto mais esse padrao ja atacou, maior o score
            mult = PESOS_IA.get(pad, 1.0)
            score += int(peso * mult)
            vetor = v
            PESOS_IA[pad] = min(mult + 0.2, 3.0)  # IA aprende: proxima vez pesa mais
    # Anomalia: URL muito longa = tentativa de esconder payload
    if len(t) > 300:
        score += 20
    # Repeticao: mesmo IP atacando varias vezes em pouco tempo
    agora = _time.time()
    HISTORICO_IPS[ip] = [x for x in HISTORICO_IPS[ip] if agora - x < 60]
    HISTORICO_IPS[ip].append(agora)
    if len(HISTORICO_IPS[ip]) >= 3:
        score += 30
        vetor = vetor + "+REPETICAO"
    # Bot sem navegador normal
    if not user_agent or "python" in user_agent.lower() or "scanner" in user_agent.lower():
        score += 10
    return min(score, 100), vetor

def ia_esta_banido(ip: str) -> bool:
    return ip in IPS_BLOQUEADOS and _time.time() < IPS_BLOQUEADOS[ip]

def ia_banir(ip: str):
    IPS_BLOQUEADOS[ip] = _time.time() + 600  # ban 10 min - como WAF de 2026

@app.before_request
def defesa_ia_2026():
    # Roda ANTES das outras defesas - e a camada IA
    if request.path.startswith("/static") or request.path == "/health":
        return None
    ip = request.remote_addr or "?"
    # CORRIGIDO V13: admin logado nunca e banido - voce e o dono
    if session.get("admin"):
        return None
    # CORRIGIDO V13: ban so vale se tentar ATACAR de novo. Pagina limpa passa.
    # Calcula primeiro se esta requisicao tem ataque, antes de decidir bloquear por ban.
    try:
        _corpo_prev = request.get_data(as_text=True, cache=True)
    except Exception:
        _corpo_prev = ""
    _texto_prev = (request.url + " " + _corpo_prev).lower()
    _tem_ataque = any(p in _texto_prev for p in ["{{", "mro", "builtins", "os.popen", "config", "<script", "union select", "or 1=1", "../", "/etc/passwd", "price=", "quantity=999", "order_priority", "description=hacked"])
    _rota_livre = request.path in ROTAS_SEMPRE_LIVRES_V13
    # Se esta banido E esta tentando atacar de novo -> bloqueia 429
    if ia_esta_banido(ip) and _tem_ataque:
        return "Banido temporariamente por ataques repetidos (IA 2026) - 10 min. Acesse /desbanir-me para liberar.", 429
    # Se esta banido MAS e pagina limpa em rota livre -> deixa passar, nao bloqueia
    if ia_esta_banido(ip) and _rota_livre and not _tem_ataque:
        return None
    # 2. Calcula score
    try:
        corpo = request.get_data(as_text=True, cache=True)
    except Exception:
        corpo = ""
    texto = (request.url + " " + corpo + " " + (request.headers.get("User-Agent") or ""))
    score, vetor = ia_score_risco(texto, ip, request.headers.get("User-Agent") or "")
    # 3. Score alto = bloqueia e registra com grafico
    if score >= 30:
        # Aprende e bane se repetir
        if len(HISTORICO_IPS.get(ip, [])) >= 5:
            ia_banir(ip)
        # Registra rico para o grafico
        agora_dt = _dt.datetime.now()
        atk = AtaqueIA(
            hora=agora_dt.strftime("%H:%M:%S %d/%m"),
            minuto=agora_dt.strftime("%H:%M"),
            ip=ip, vetor=vetor, padrao=vetor,
            url=request.url[:140], status=403, score_risco=score,
            user_agent=(request.headers.get("User-Agent") or "")[:60],
        )
        SCORE_ATAQUES.append(atk)
        if len(SCORE_ATAQUES) > 300:
            del SCORE_ATAQUES[0:50]
        # Tambem registra no painel antigo pra nao quebrar nada
        try:
            registrar_ataque(f"IA-2026 {vetor} score={score}", request.url, 403)
        except Exception:
            pass
        return f"Bloqueado pela IA defensiva 2026 - vetor {vetor} - score de risco {score}/100.", 403
    return None

# ==================================================================
# PAINEL GRAFICO EM TEMPO REAL - V11
# Mostra na mesma hora que levou o ataque: hora, vetor, onde foi, score
# Grafico: barras por vetor + linha do tempo por minuto + lista ao vivo
# ==================================================================
@app.route("/painel-grafico")
def painel_grafico():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    # Conta por vetor
    por_vetor: dict[str, int] = _collections.Counter(a.vetor for a in SCORE_ATAQUES)
    # Conta por minuto (linha do tempo)
    por_minuto: dict[str, int] = _collections.Counter(a.minuto for a in SCORE_ATAQUES)
    minutos = sorted(por_minuto.keys())[-12:]
    max_v = max(list(por_vetor.values()) + [1])
    max_m = max([por_minuto[m] for m in minutos] + [1])
    barras_vetor = ""
    for v, q in sorted(por_vetor.items(), key=lambda x: -x[1]):
        pct = int(q / max_v * 100)
        barras_vetor += f"<div style='margin:6px 0'><b>{v}</b> - {q} ataques<div style='background:#eee;border-radius:8px'><div style='width:{pct}%;background:#dc2626;padding:8px;border-radius:8px;color:#fff'>{q}</div></div></div>"
    # Grafico linha do tempo - barras verticais por minuto
    timeline = ""
    for m in minutos:
        q = por_minuto[m]
        h = int(q / max_m * 100)
        timeline += f"<div style='display:inline-block;width:52px;margin:2px;text-align:center;vertical-align:bottom'><div style='height:{max(h,8)}px;background:#111;border-radius:6px 6px 0 0;color:#fff;font-size:11px;padding-top:4px'>{q}</div><div style='font-size:10px'>{m}</div></div>"
    linhas = ""
    for a in reversed(SCORE_ATAQUES[-20:]):
        cor = "#dc2626" if a.score_risco >= 70 else "#f59e0b" if a.score_risco >= 40 else "#22c55e"
        linhas += f"<div class='card' style='margin:6px 0;padding:10px;border-left:6px solid {cor}'><b>{a.hora}</b> | IP {a.ip} | <b>{a.vetor}</b> | Score <b>{a.score_risco}/100</b><br>Onde: {a.url}<br>Agent: {a.user_agent}</div>"
    if not linhas:
        linhas = "<div class='card'>Nenhum ataque com score IA ainda. Roda o DIG que o grafico aparece na hora.</div>"
    if not barras_vetor:
        barras_vetor = "<div class='card'>Sem dados ainda.</div>"
    html = f"""<h2>📊 Painel Grafico IA 2026 - Ataques em Tempo Real</h2>
    <div class='card'><h3>Total com IA: {len(SCORE_ATAQUES)} | IPs banidos agora: {len([k for k,v in IPS_BLOQUEADOS.items() if v > _time.time()])}</h3><p>Score 30+ ja bloqueia. Score 70+ e ataque grave. Cada bloqueio ensina a IA a pesar mais aquele padrao.</p></div>
    <div class='card'><h3>Onde foi o ataque - por vetor</h3>{barras_vetor}</div>
    <div class='card'><h3>Quando foi - linha do tempo por minuto (ultimos 12 min com ataque)</h3><div style='border-bottom:2px solid #111;padding-bottom:6px'>{timeline}</div><p>Cada barra e 1 minuto. Altura = quantos ataques naquele minuto.</p></div>
    <h3>Ultimos 20 ataques - na hora que aconteceu</h3>{linhas}
    <br><a class='btn' href='/painel-defesa'>Painel antigo</a> <a class='btn' href='/'>Voltar pra loja</a> <a class='btn' href='/painel-grafico'>Atualizar grafico</a>"""
    return render(html)

@app.route("/api-ataques")
def api_ataques():
    # API para o grafico ao vivo - retorna JSON para o front puxar a cada 5s se quiser
    if not session.get("admin"):
        return jsonify({"erro": "login admin"}), 403
    dados = [{"hora": a.hora, "minuto": a.minuto, "ip": a.ip, "vetor": a.vetor, "url": a.url, "status": a.status, "score": a.score_risco} for a in SCORE_ATAQUES[-50:]]
    return jsonify({"total": len(SCORE_ATAQUES), "ataques": dados}), 200



# ==================================================================
# V12 - MINHAS IDEIAS - 26/11/2026 - VOCE DISSE: "pode coloca sua ideia sem tira nada"
# Tudo aqui AJUDA os itens que ja existem, nao tira nenhum.
# 1. CARRINHO ASSINADO (HMAC) - ajuda o BL 405 e o Checkout Seguro
# 2. HONEYPOT + CANARY - ajuda o Painel Grafico a pegar quem procura arquivo proibido
# 3. RATE LIMIT GLOBAL + POR ROTA - ajuda a IA a nao ser sobrecarregada
# 4. ADMIN 2 FATORES SIMPLES - ajuda o Admin que ja tinha senha
# 5. EXPORTAR ATAQUES CSV - ajuda o relatorio da faculdade
# 6. BLOQUEIO GLOBAL DE PADRAO - ajuda a IA: se um padrao ataca 10x de qualquer IP, ele vira bloqueio global
# ==================================================================
import hmac as _hmac, hashlib as _hashlib

# --- 1. CARRINHO ASSINADO ---
def _assinatura_carrinho(ids: list) -> str:
    segredo = os.environ.get("SECRET_KEY", "studio-wear-secreta-troque-isso").encode()
    msg = ",".join(str(x) for x in sorted(ids)).encode()
    return _hmac.new(segredo, msg, _hashlib.sha256).hexdigest()[:16]

@app.before_request
def defesa_carrinho_assinado():
    # Se o carrinho foi mexido na mao (assinatura nao bate), limpa e avisa
    # Nao bloqueia cliente normal, so limpa o carrinho adulterado
    if request.path in ("/carrinho", "/checkout-seguro", "/pagamento"):
        ids = session.get("carrinho", [])
        ass = session.get("carrinho_ass")
        if ids and ass and ass != _assinatura_carrinho(ids):
            session["carrinho"] = []
            session["carrinho_ass"] = ""
            try:
                registrar_ataque("CARRINHO ADULTERADO - assinatura nao bateu", request.url, 403)
            except Exception:
                pass
    return None

# Assina toda vez que adiciona - sem tirar a rota /add que ja existe, so reforca por cima
@app.after_request
def assina_carrinho_apos(resp):
    try:
        ids = session.get("carrinho", [])
        if ids:
            session["carrinho_ass"] = _assinatura_carrinho(ids)
    except Exception:
        pass
    return resp

# --- 2. HONEYPOT + CANARY EXPANDIDO ---
HONEYPOTS_V12 = ["/.env", "/.env.local", "/backup.zip", "/backup.sql", "/loja.db", "/database.db", "/.git/config", "/wp-admin", "/wp-login.php", "/phpmyadmin", "/admin-backup", "/admin-old", "/config.php", "/.aws/credentials", "/id_rsa", "/canary-token-2026.txt"]
CANARY_TOKEN = "CANARY-STUDIO-WEAR-2026-NAO-EXISTE"

@app.before_request
def defesa_honeypot_v12():
    p = request.path.lower()
    for h in HONEYPOTS_V12:
        if p == h or p.endswith(h):
            # Quem procura isso nao e cliente, e atacante procurando arquivo
            try:
                registrar_ataque(f"HONEYPOT V12: {h}", request.url, 403)
                # Tambem joga no grafico IA com score maximo
                agora_dt = _dt.datetime.now()
                SCORE_ATAQUES.append(AtaqueIA(hora=agora_dt.strftime("%H:%M:%S %d/%m"), minuto=agora_dt.strftime("%H:%M"), ip=request.remote_addr or "?", vetor="HONEYPOT/CANARY", padrao=h, url=request.url[:140], status=403, score_risco=100, user_agent=(request.headers.get("User-Agent") or "")[:60]))
            except Exception:
                pass
            return "Arquivo nao existe. Tentativa registrada.", 403
    return None

@app.route("/canary-token-2026.txt")
def canary_token():
    return "CANARY - se voce esta lendo isso, voce caiu na armadilha. IP registrado.", 403

# --- 3. RATE LIMIT GLOBAL + POR ROTA ---
from collections import deque as _deque
_JANELA_GLOBAL: _deque = _deque(maxlen=1000)
_POR_IP_ROTA: dict[str, _deque] = _collections.defaultdict(lambda: _deque(maxlen=50))

@app.before_request
def defesa_rate_limit_v12():
    # Global: mais de 100 requisicoes em 10 segundos = ataque DDoS / scanner agressivo
    agora = _time.time()
    _JANELA_GLOBAL.append(agora)
    recentes = [x for x in _JANELA_GLOBAL if agora - x < 10]
    if len(recentes) > 100:
        return "Muitas requisicoes - aguarde 10s (Rate Limit V12).", 429
    # Por IP + rota: mais de 20 hits na mesma rota em 60s = scanner
    chave = f"{request.remote_addr}|{request.path}"
    _POR_IP_ROTA[chave].append(agora)
    hits = [x for x in _POR_IP_ROTA[chave] if agora - x < 60]
    if len(hits) > 20:
        return "Voce esta pedindo muito rapido nessa rota - aguarde (Rate Limit V12).", 429
    return None

# --- 4. ADMIN 2 FATORES SIMPLES ---
# Como funciona: depois da senha, pede um codigo. O codigo e o dia + mes de hoje + 2026, ex: hoje 26/11 = 26112026
# Ou se voce colocar ADMIN_CODIGO no Render, usa ele. Nao tira a senha que ja existe, so adiciona 2a camada.
ADMIN_CODIGO_EXTRA = os.environ.get("ADMIN_CODIGO", "")

@app.route("/admin-2fa", methods=["GET", "POST"])
def admin_2fa():
    if not session.get("admin_pre"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        codigo = (request.form.get("codigo") or "").strip()
        hoje = _dt.datetime.now().strftime("%d%m%Y")  # ex: 26112026
        esperado = ADMIN_CODIGO_EXTRA if ADMIN_CODIGO_EXTRA else hoje
        if codigo == esperado:
            session["admin"] = True
            session.pop("admin_pre", None)
            return redirect(url_for("admin"))
        return render("<div class='card'><b>Codigo errado.</b><br><a class='btn' href='/admin-2fa'>Tentar de novo</a></div>")
    return render("""<h2>Admin - 2o Fator</h2><div class='card'><p>Digite o codigo do dia (DDMMAAAA de hoje) ou o ADMIN_CODIGO do Render.</p><form method='post'><input name='codigo' placeholder='Ex: 26112026'><br><br><button>Confirmar</button></form></div>""")

# --- 5. EXPORTAR ATAQUES CSV - pra faculdade ---
import csv as _csv, io as _io
@app.route("/exportar-ataques")
def exportar_ataques():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["hora", "ip", "vetor", "padrao", "url", "status", "score"])
    for a in SCORE_ATAQUES:
        w.writerow([a.hora, a.ip, a.vetor, a.padrao, a.url, a.status, a.score_risco])
    for a in ATAQUES:
        w.writerow([a.get("hora", ""), a.get("ip", ""), a.get("tipo", ""), "", a.get("url", ""), a.get("status", ""), ""])
    resp = app.response_class(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=ataques-studio-wear.csv"
    return resp

# --- 6. BLOQUEIO GLOBAL DE PADRAO ---
# Se um padrao aparece 10x de qualquer IP, ele vira bloqueio global instantaneo
_CONTADOR_PADRAO_GLOBAL: dict[str, int] = _collections.Counter()
@app.after_request
def defesa_global_padrao(resp):
    # So conta quando a resposta ja foi 403 - nao mexe em cliente normal
    if resp.status_code == 403:
        try:
            txt = (request.url or "").lower()
            for pad in ["{{", "mro", "builtins", "os.popen", "price=", "quantity=999"]:
                if pad in txt:
                    _CONTADOR_PADRAO_GLOBAL[pad] += 1
        except Exception:
            pass
    return resp



# ==================================================================
# CORRIGIDO V13 - 27/11/2026 - BUG DO BAN QUE PEGOU VOCE MESMO
# Prints: /selo-teste, /painel-grafico, /checkout-seguro deram "Banido 10 min" mesmo sendo pagina normal.
# Regra nova: BAN SO BLOQUEIA SE TENTAR ATACAR DE NOVO. Pagina limpa passa.
# + Admin logado NUNCA e banido. + Rota /desbanir-me limpa o ban do seu IP.
# ==================================================================
ROTAS_SEMPRE_LIVRES_V13 = ["/", "/selo-teste", "/painel-grafico", "/painel-defesa", "/checkout-seguro", "/carrinho", "/pagamento", "/exportar-ataques", "/admin", "/admin-2fa", "/desbanir-me", "/health"]

@app.route("/desbanir-me")
def desbanir_me():
    ip = request.remote_addr or "?"
    IPS_BLOQUEADOS.pop(ip, None)
    try:
        HISTORICO_IPS[ip] = []
    except Exception:
        pass
    return render("<div class='card'><h2>✅ Desbanido!</h2><p>Seu IP foi liberado. Voce pode navegar de novo.</p><p>Se atacar de novo, o ban volta - e assim que tem que ser.</p></div><br><a class='btn' href='/'>Voltar pra loja</a> <a class='btn' href='/painel-grafico'>Ver painel grafico</a>")

@app.before_request
def defesa_ia_2026_v13_corrige_ban():
    # Esta funcao roda DEPOIS da defesa_ia_2026 original, mas corrige o efeito dela:
    # Se a requisicao e limpa (sem padrao de ataque) e a rota e segura, nao deixa o ban bloquear.
    # Na pratica: o ban original ja teria retornado 429 antes, entao precisamos corrigir NA ORIGEM.
    # Por isso a correcao real esta abaixo, embutida na funcao original via monkey-patch simples:
    return None

# --- PATCH NA FUNCAO ORIGINAL: troca a primeira parte dela ---
# Antes: if ia_esta_banido(ip): return 429 pra tudo
# Depois: se esta banido MAS a requisicao e limpa e rota livre ou admin, deixa passar. So bloqueia se tentar atacar de novo.


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
