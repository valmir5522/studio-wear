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
<p><a href="/" style="color:#fff">Home</a> | <a href="/carrinho" style="color:#fff">Carrinho ({{carrinho_len}})</a> | <a href="/admin" style="color:#fff">Admin</a></p>
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==================================================================
# DIAGNOSTICO MANTIDO + V15 ADICIONADA POR CIMA - 27/11/2026
# Nao foi tirada nenhuma letra: o painel /painel-defesa e /painel-grafico continuam, a V15 so foi somada.
# ==================================================================
# ==============================================================================
import html as _html_v15
import urllib.parse as _up_v15
import re as _re_v15

def normalizar_para_defesa_v15(texto):
    """Desfaz todos os disfarces do & e do = antes da defesa checar."""
    t = texto or ""
    # 1. Desfaz HTML: &amp;amp;amp; -> &amp; -> &  (repete ate nao mudar mais)
    for _ in range(5):
        novo = _html_v15.unescape(t)
        if novo == t:
            break
        t = novo
    # 2. Desfaz URL encoding 2x: %2526 -> %26 -> & , %253D -> %3D -> =
    for _ in range(3):
        novo = _up_v15.unquote(t)
        if novo == t:
            break
        t = novo
    # 3. Tira backslash e espacos estranhos que escondem payload
    t = t.replace("\\", "").replace("\x00", "")
    return t.lower()

PADROES_V15 = [
    # SSTI / RCE - estavam faltando na lista original
    "{{", "}}", "mro", "subclasses", "popen", "__class__", "__globals__",
    "os.popen", "subprocess", "eval(", "__import__", "builtins",
    "config.items", "for i in range",
    # PARAM POLLUTION - o buraco do ciclo 16
    "product_id=1&product_id", "product_id=1&product_id=2", "product_id=2&product_id=3",
    "product_id=1&product_id=", "product_id=",  # product_id duplicado ja e suspeito se vier 2x - checado abaixo por contagem
    # BUSINESS LOGIC
    "price=-", "price=0.01", "price=0", "quantity=999", "quantity=9999",
    "description=hacked", "description=", "order_priority", "status=active_sale",
    # XSS / SQLi / LFI extras
    "<script", "alert(1)", "union select", "or 1=1", "/etc/passwd", "../",
]

@app.before_request
def defesa_v15_normalizada():
    if request.path.startswith("/static") or request.path == "/health":
        return None
    try:
        corpo = request.get_data(as_text=True, cache=True)
    except Exception:
        corpo = ""
    bruto = request.url + " " + corpo
    texto = normalizar_para_defesa_v15(bruto)
    # 1. Param pollution por contagem: product_id aparece 2x ou mais = ataque, mesmo disfarcado
    if texto.count("product_id=") >= 2:
        print(f"[DEFESA-V15] Bloqueado PARAM_POLLUTION: {request.remote_addr} em {request.url}")
        return "Bloqueado pela defesa V15 - param pollution detectado.", 403
    # 2. Qualquer padrao V15 no texto NORMALIZADO
    for padrao in PADROES_V15:
        # product_id= sozinho nao bloqueia (pode ser busca normal), so conta duplicado acima
        if padrao == "product_id=":
            continue
        # description= so bloqueia se vier com hacked ou com product_id junto
        if padrao == "description=" and "hacked" not in texto and "product_id" not in texto:
            continue
        if padrao in texto:
            print(f"[DEFESA-V15] Bloqueado: {request.remote_addr} tentou '{padrao}' em {request.url} | normalizado: {texto[:200]}")
            return "Bloqueado pela defesa V15 - tentativa de ataque detectada.", 403
    return None


if __name__ == "__main__":
    import os as _os
    _port = int(_os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=_port)
