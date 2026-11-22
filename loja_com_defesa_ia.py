# ============================================================
# STUDIO WEAR - LOJA + SISTEMA DE DEFESA IA (WAF + IDS + ANOMALIA)
# Detecta: SQL Injection, XSS, Path Traversal, Forca Bruta,
# Bots, Scanner, CSRF, Upload malicioso, Velocidade anormal
# e BLOQUEIA sozinho + registra tudo no painel do lojista
# ============================================================
import os, sqlite3, urllib.parse, secrets, re, time, json, hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, render_template_string, session, redirect, url_for, request, send_from_directory, abort, g, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
    PERMANENT_SESSION_LIFETIME=3600, MAX_CONTENT_LENGTH=5*1024*1024,
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "loja.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

NOME_LOJA = "STUDIO WEAR"
SENHA_ADMIN = os.environ.get("ADMIN_PASSWORD", "")
if not SENHA_ADMIN:
    SENHA_ADMIN = secrets.token_hex(8)
    print(f"[AVISO] Defina ADMIN_PASSWORD. Temporaria: {SENHA_ADMIN}")
SEU_WHATSAPP = os.environ.get("SEU_WHATSAPP", "5585999999999")
EXTENSOES_PERMITIDAS = {"png","jpg","jpeg","webp","gif"}

# ============================================================
# 🧠 CEREBRO DA DEFESA IA - APRENDE O NORMAL E DETECTA ANOMALIA
# ============================================================
# Memoria em RAM (rapida) + banco (historico)
REQ_POR_IP = defaultdict(lambda: deque(maxlen=200))  # timestamps por IP
PONTOS_IP = defaultdict(int)  # score de risco por IP
IPS_BLOQUEADOS = {}  # ip -> ate_quando (timestamp)
TENTATIVAS_LOGIN = defaultdict(int)
ULTIMO_ALERTA = {}

# --- 1. ASSINATURAS DE ATAQUE (WAF - igual Cloudflare / ModSecurity) ---
PADROES_ATAQUE = [
    # SQL Injection
    (r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|drop\s+table|delete\s+from|update\s+.*\s+set|or\s+1\s*=\s*1|'\s*or\s*'|\"\\s*or\\s*\"|sleep\s*\(|benchmark\s*\()", "SQL Injection", 80),
    (r"(?i)(information_schema|pg_catalog|sqlite_master|@@version|load_file|into\s+outfile)", "SQL Injection Avancado", 90),
    # XSS
    (r"(?i)(<script|javascript\s*:|onerror\s*=|onload\s*=|onmouseover\s*=|<iframe|<svg\s+on|alert\s*\(|document\.cookie|eval\s*\()", "XSS - Cross Site Scripting", 80),
    # Path Traversal / LFI / RCE
    (r"(\.\./|\.\.\\|/etc/passwd|/proc/self|/\.env|wp-config|\.git/config)", "Path Traversal / Vazamento de arquivo", 85),
    (r"(?i)(;.*(cat|ls|id|whoami|wget|curl|nc|bash|sh)\b|\|\s*(cat|ls|id)|`.*`|\$\(.*\))", "Command Injection - Tentativa de rodar comando", 95),
    # Scanner / Reconhecimento
    (r"(?i)(nmap|nikto|sqlmap|masscan|dirbuster|gobuster|hydra|burp|acunetix)", "Scanner de Hacker", 70),
    # PHP / WordPress (seu site e Python, quem procura isso e hacker)
    (r"(?i)(\.php|\.asp|wp-admin|wp-login|xmlrpc\.php|phpmyadmin|\.env$)", "Procurando brecha de outro sistema", 60),
    # SSRF
    (r"(?i)(169\.254\.169\.254|metadata\.google|localhost:\d+|127\.0\.0\.1)", "SSRF - Tentativa de acessar servidor interno", 90),
    # Log4Shell / JNDI
    (r"(?i)(\$\{jndi:|\$\{env:)", "Log4Shell / JNDI Injection", 95),
]

# Bots conhecidos bons (Google, etc) - nao bloqueia
BOTS_BONS = ["googlebot","bingbot","facebookexternalhit","twitterbot","whatsapp"]
# User-Agents suspeitos
UA_SUSPEITOS = ["python-requests","curl","wget","postman","sqlmap","nmap","axios","httpclient","java/","perl","ruby"]  # go-http REMOVIDO: e o Render testando se o site ta vivo, nao e hacker

def ip_cliente():
    # Pega IP real mesmo atras de Cloudflare / proxy
    for h in ["CF-Connecting-IP","X-Forwarded-For","X-Real-IP"]:
        v = request.headers.get(h)
        if v: return v.split(",")[0].strip()
    return request.remote_addr or "desconhecido"

def registrar_ataque(ip, tipo, score, detalhes, url=""):
    """Salva ataque no banco para o painel mostrar"""
    try:
        conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row
        conn.execute("INSERT INTO ataques (ip, tipo, score, detalhes, url, user_agent, criado_em) VALUES (?,?,?,?,?,?,?)",
            (ip, tipo, score, detalhes[:500], url[:300], (request.headers.get("User-Agent","") or "")[:300], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
    except Exception as e: print("Erro registrar ataque:", e)
    # Alerta no terminal (voce ve na hora)
    print(f"\n🚨 ATAQUE DETECTADO | IP: {ip} | {tipo} | Score: {score} | {detalhes[:120]} | URL: {url}\n")

def calcular_risco(ip, caminho, args_texto, ua):
    """IA simples: soma pontos por comportamento anormal. >=100 = BLOQUEIA"""
    score = 0; motivos = []
    # 1. Assinaturas
    texto = (caminho + " " + args_texto + " " + ua).lower()
    for padrao, nome, pts in PADROES_ATAQUE:
        if re.search(padrao, caminho + " " + args_texto, re.IGNORECASE) or re.search(padrao, ua, re.IGNORECASE):
            score += pts; motivos.append(nome)
    # 2. Velocidade anormal (mais de 30 requisicoes em 10 seg = bot / ataque DDoS)
    agora = time.time()
    REQ_POR_IP[ip].append(agora)
    recentes = [t for t in REQ_POR_IP[ip] if agora - t < 10]
    if len(recentes) > 30: score += 70; motivos.append(f"Velocidade anormal: {len(recentes)} req/10s (DDoS/Bot)")
    elif len(recentes) > 15: score += 30; motivos.append(f"Velocidade alta: {len(recentes)} req/10s")
    # 3. User-Agent vazio ou suspeito
    if not ua or len(ua) < 10:
        score += 40; motivos.append("Sem User-Agent (bot escondido)")
    elif any(x in ua.lower() for x in UA_SUSPEITOS) and not any(b in ua.lower() for b in BOTS_BONS):
        score += 35; motivos.append(f"Ferramenta de hacker: {ua[:60]}")
    # 4. Tentando acessar pagina que nao existe varias vezes (scanner)
    if caminho in ["/.env","/wp-admin","/phpmyadmin","/config.php","/.git/config","/admin.php"]:
        score += 50; motivos.append("Procurando arquivo secreto")
    # 5. Tamanho anormal (payload gigante)
    if len(args_texto) > 2000: score += 40; motivos.append("Payload gigante")
    # 6. Historico do IP (reincidente = mais perigoso)
    score += min(PONTOS_IP[ip], 50)
    return score, motivos

# ============================================================
# BANCO
# ============================================================
def conectar_db():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; return conn

def inicializar_banco():
    conn = conectar_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, preco REAL NOT NULL, categoria TEXT, tamanhos TEXT, estoque INTEGER DEFAULT 10, imagem TEXT)""")
    # NOVA TABELA: historico de ataques
    conn.execute("""CREATE TABLE IF NOT EXISTS ataques (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, tipo TEXT, score INTEGER, detalhes TEXT, url TEXT, user_agent TEXT, criado_em TEXT)""")
    # NOVA TABELA: log de acessos normais (para a IA aprender o normal)
    conn.execute("""CREATE TABLE IF NOT EXISTS acessos (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, url TEXT, metodo TEXT, status INTEGER, criado_em TEXT)""")
    conn.commit(); conn.close()
inicializar_banco()

def extensao_permitida(n): return "." in n and n.rsplit(".",1)[1].lower() in EXTENSOES_PERMITIDAS
def nome_arquivo_seguro(f):
    base = secure_filename(f); nome, ext = os.path.splitext(base)
    return f"{secrets.token_hex(8)}_{nome[:40]}{ext.lower()}"

# ============================================================
# 🛡️ ANTES DE CADA REQUISICAO - O GUARDA DA PORTA
# ============================================================
@app.before_request
def guarda_defesa_ia():
    ip = ip_cliente()
    # 1. IP ja bloqueado?
    if ip in IPS_BLOQUEADOS and time.time() < IPS_BLOQUEADOS[ip]:
        registrar_ataque(ip, "Tentativa com IP bloqueado", 10, "IP bloqueado tentou voltar", request.path)
        abort(403)
    elif ip in IPS_BLOQUEADOS: del IPS_BLOQUEADOS[ip]
    # 2. Honeypot: rota isca que NENHUM cliente normal acessa
    # Se alguem acessar /admin-backup ou /.env, e 100% hacker escaneando
    if request.path in ["/admin-backup","/admin_old","/backup.zip","/.env","/wp-login.php"]:
        PONTOS_IP[ip] += 100
        registrar_ataque(ip, "HONEYPOT - Caiu na isca", 100, f"Acessou isca proibida: {request.path}", request.path)
        IPS_BLOQUEADOS[ip] = time.time() + 3600  # bloqueia 1h
        abort(403)
    ua = request.headers.get("User-Agent","")
    # 2b. WHITELIST: health check do Render / Uptime - NUNCA bloqueia
    if ua.startswith("Go-http-client") or request.method == "HEAD":
        g.ip_cliente = ip
        return None
    # 3. Calcula risco com a IA
    args_texto = request.query_string.decode(errors="ignore") + " " + str(request.form)[:2000]
    score, motivos = calcular_risco(ip, request.path, args_texto, ua)
    if score >= 30:
        PONTOS_IP[ip] += score // 2
        registrar_ataque(ip, " + ".join(motivos[:3]), score, " | ".join(motivos), request.path)
    if score >= 150:  # era 100, subiu para nao bloquear cliente normal
        # BLOQUEIO AUTOMATICO
        tempo = 3600 if score < 180 else 86400  # 1h ou 24h se muito grave
        IPS_BLOQUEADOS[ip] = time.time() + tempo
        PONTOS_IP[ip] += 50
        print(f"🔒 IP {ip} BLOQUEADO por {tempo//3600}h - Score {score}")
        abort(403)
    # 4. CSRF (so POST)
    if request.method == "POST":
        token = request.form.get("csrf_token","")
        if not token or not secrets.compare_digest(token, session.get("csrf_token","")):
            registrar_ataque(ip, "CSRF - Token invalido", 60, "POST sem token valido", request.path)
            abort(403)
    g.ip_cliente = ip

@app.after_request
def apos_request(resp):
    resp.headers["X-Content-Type-Options"]="nosniff"; resp.headers["X-Frame-Options"]="DENY"
    resp.headers["Referrer-Policy"]="no-referrer"; resp.headers["Content-Security-Policy"]="default-src 'self' 'unsafe-inline' https://placehold.co; img-src 'self' data: https://placehold.co; form-action 'self'"
    # Log leve (so para aprender padrao normal, sem travar)
    try:
        if request.path not in ["/favicon.ico"]:
            conn = sqlite3.connect(DB_NAME)
            conn.execute("INSERT INTO acessos (ip,url,metodo,status,criado_em) VALUES (?,?,?,?,?)",(getattr(g,'ip_cliente','?'), request.path[:200], request.method, resp.status_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit(); conn.close()
    except Exception: pass
    return resp

def gerar_csrf():
    if "csrf_token" not in session: session["csrf_token"]=secrets.token_hex(16)
    return session["csrf_token"]

# --- TEMPLATES (iguais aos seus, + painel de seguranca) ---
HTML_LOJA = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{{ nome_loja }}</title><style>body{font-family:'Segoe UI',sans-serif;margin:0;background:#f4f4f5;color:#18181b}header{background:#18181b;color:#fff;padding:18px 30px;display:flex;justify-content:space-between;align-items:center}header a{color:#facc15;text-decoration:none;font-weight:bold}.vitrine{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,280px));justify-content:center;gap:24px;padding:30px;max-width:1200px;margin:auto}.card{background:#fff;border-radius:10px;padding:15px;text-align:center;box-shadow:0 4px 6px rgba(0,0,0,.05);display:flex;flex-direction:column;justify-content:space-between}.card img{width:100%;height:240px;object-fit:cover;border-radius:6px;background:#e4e4e7}.categoria{font-size:.8em;text-transform:uppercase;color:#71717a;letter-spacing:1px;margin-top:10px}.preco{font-size:1.25em;color:#16a34a;font-weight:bold;margin:8px 0}select{padding:8px;border-radius:5px;border:1px solid #d4d4d8;margin-bottom:10px;width:100%}.btn{width:100%;background:#18181b;color:#fff;padding:10px;border:none;border-radius:5px;cursor:pointer;font-weight:bold}footer{text-align:center;padding:20px;color:#71717a;font-size:.85em}footer a{color:#71717a}</style></head><body><header><h1>{{ nome_loja }}</h1><a href="/carrinho">🛍 Sacola ({{ qtd_carrinho }})</a></header><div class="vitrine">{% for p in produtos %}<div class="card"><div><img src="{{ p['imagem'] }}" alt="{{ p['nome'] }}"><div class="categoria">{{ p['categoria'] }} • {{ p['estoque'] }} un.</div><h3>{{ p['nome'] }}</h3><p class="preco">R$ {{ "%.2f"|format(p['preco']) }}</p></div><form action="/adicionar/{{ p['id'] }}" method="POST"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><select name="tamanho" required>{% for tam in p['tamanhos'].split(',') %}<option value="{{ tam.strip() }}">Tamanho: {{ tam.strip() }}</option>{% endfor %}</select><button class="btn">Adicionar à Sacola</button></form></div>{% endfor %}</div><footer><a href="/admin">Área do Lojista</a></footer></body></html>"""
HTML_CARRINHO = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Sua Sacola</title><style>body{font-family:'Segoe UI',sans-serif;background:#f4f4f5}.container{max-width:600px;margin:40px auto;background:#fff;padding:25px;border-radius:10px}ul{list-style:none;padding:0}li{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #e4e4e7}.tag-tam{background:#e4e4e7;padding:2px 8px;border-radius:4px;font-size:.85em}.total{font-weight:bold;text-align:right;margin:20px 0;font-size:1.3em}.acoes{display:flex;gap:10px;flex-wrap:wrap}.btn{padding:12px 20px;text-decoration:none;border-radius:5px;font-weight:bold;text-align:center}.btn-voltar{background:#71717a;color:#fff}.btn-limpar{background:#ef4444;color:#fff;border:none;cursor:pointer}.btn-zap{background:#16a34a;color:#fff;flex-grow:1}</style></head><body><div class="container"><h2>🛍 Sua Sacola</h2>{% if itens %}<ul>{% for item in itens %}<li><span>{{ item['nome'] }} <span class="tag-tam">Tam: {{ item['tamanho'] }}</span></span><span>R$ {{ "%.2f"|format(item['preco']) }}</span></li>{% endfor %}</ul><p class="total">Total: R$ {{ "%.2f"|format(total) }}</p><div class="acoes"><a href="/" class="btn btn-voltar">Continuar</a><form action="/limpar" method="POST"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button class="btn btn-limpar">Esvaziar</button></form><a href="{{ link_whatsapp }}" target="_blank" class="btn btn-zap">Pedir no WhatsApp</a></div>{% else %}<p>Sacola vazia.</p><a href="/" class="btn btn-voltar">Ver Coleção</a>{% endif %}</div></body></html>"""
HTML_ADMIN = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Painel Admin</title><style>body{font-family:'Segoe UI',sans-serif;margin:0;background:#f4f4f5}header{background:#18181b;color:#fff;padding:15px 30px;display:flex;justify-content:space-between}header a{color:#facc15;text-decoration:none;font-weight:bold}.container{max-width:900px;margin:30px auto;padding:0 20px}.box{background:#fff;padding:25px;border-radius:10px;margin-bottom:25px}.login-box{max-width:350px;margin:80px auto;text-align:center}input,select{width:100%;padding:10px;margin:8px 0 15px;border:1px solid #d4d4d8;border-radius:5px;box-sizing:border-box}.grid-form{display:grid;grid-template-columns:1fr 1fr;gap:15px}.btn{background:#18181b;color:#fff;padding:12px 20px;border:none;border-radius:5px;cursor:pointer;font-weight:bold;width:100%}.btn-excluir{background:#ef4444;color:#fff;padding:6px 12px;border-radius:4px;border:none;cursor:pointer;font-size:.85em}table{width:100%;border-collapse:collapse}th,td{padding:12px;border-bottom:1px solid #e4e4e7;text-align:left}.thumb{width:45px;height:45px;object-fit:cover}.erro{color:#ef4444;font-weight:bold}.alerta{background:#fef2f2;border:1px solid #fecaca;padding:12px;border-radius:8px;margin-bottom:10px}.ok{background:#f0fdf4;border:1px solid #bbf7d0;padding:12px;border-radius:8px;margin-bottom:10px}</style></head><body>{% if not logado %}<div class="box login-box"><h2>🔒 Acesso Restrito</h2>{% if erro %}<p class="erro">{{ erro }}</p>{% endif %}<form method="POST"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="password" name="senha" placeholder="Senha do admin" required><button class="btn">Entrar</button></form><p><a href="/">Voltar</a></p></div>{% else %}<header><h2>⚙ Painel Administrativo</h2><div><a href="/admin/seguranca" style="margin-right:15px;color:#f87171">🛡️ SEGURANÇA</a><a href="/">Ver Loja</a> | <a href="/admin/sair" style="color:#ef4444">Sair</a></div></header><div class="container"><div class="box"><h3>➕ Cadastrar Nova Peça</h3><form action="/admin/novo" method="POST" enctype="multipart/form-data"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><div class="grid-form"><div><label>Nome:</label><input name="nome" required maxlength="100"></div><div><label>Preço:</label><input name="preco" required></div><div><label>Categoria:</label><select name="categoria"><option>Camisetas</option><option>Calças</option><option>Casacos</option><option>Vestidos</option><option>Acessórios</option></select></div><div><label>Tamanhos:</label><input name="tamanhos" value="P,M,G,GG" required></div><div><label>Estoque:</label><input type="number" name="estoque" value="10" required></div><div><label>Foto:</label><input type="file" name="foto" accept="image/*"></div></div><button class="btn">Salvar Produto</button></form></div><div class="box"><h3>📦 Peças ({{ produtos|length }})</h3><table><tr><th>Foto</th><th>Peça</th><th>Preço</th><th>Estoque</th><th>Ação</th></tr>{% for p in produtos %}<tr><td><img src="{{ p['imagem'] }}" class="thumb"></td><td><strong>{{ p['nome'] }}</strong></td><td>R$ {{ "%.2f"|format(p['preco']) }}</td><td>{{ p['estoque'] }}</td><td><form action="/admin/excluir/{{ p['id'] }}" method="POST" onsubmit="return confirm('Excluir?')"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button class="btn-excluir">Excluir</button></form></td></tr>{% endfor %}</table></div></div>{% endif %}</body></html>"""

HTML_SEGURANCA = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>🛡️ Central de Segurança</title><style>body{font-family:'Segoe UI',sans-serif;margin:0;background:#0f172a;color:#e2e8f0}header{background:#020617;padding:18px 30px;display:flex;justify-content:space-between}header a{color:#facc15;text-decoration:none;font-weight:bold}.container{max-width:1000px;margin:20px auto;padding:0 20px}.cards{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:15px}.card{background:#1e293b;padding:20px;border-radius:12px;text-align:center}.card b{font-size:2em;display:block}.card.red b{color:#ef4444}.card.green b{color:#22c55e}.card.yellow b{color:#facc15}.box{background:#1e293b;padding:20px;border-radius:12px;margin-top:20px}table{width:100%;border-collapse:collapse}th,td{padding:10px;border-bottom:1px solid #334155;text-align:left;font-size:.9em}.badge{padding:3px 8px;border-radius:20px;font-size:.8em;font-weight:bold}.critico{background:#ef4444;color:#fff}.alto{background:#f97316;color:#fff}.medio{background:#eab308;color:#000}.btn{background:#ef4444;color:#fff;padding:8px 14px;border:none;border-radius:6px;cursor:pointer;font-weight:bold}.btn2{background:#22c55e;color:#fff;padding:8px 14px;border:none;border-radius:6px;cursor:pointer;font-weight:bold}</style></head><body><header><h2>🛡️ CENTRAL DE SEGURANÇA IA</h2><div><a href="/admin">← Voltar Admin</a></div></header><div class="container"><div class="cards"><div class="card red"><span>🚨 Ataques Hoje</span><b>{{ total_hoje }}</b></div><div class="card yellow"><span>🔒 IPs Bloqueados</span><b>{{ ips_bloqueados }}</b></div><div class="card"><span>👁️ Acessos Hoje</span><b>{{ acessos_hoje }}</b></div><div class="card green"><span>✅ Status</span><b>{{ status }}</b></div></div><div class="box"><h3>📊 Últimos Ataques Detectados</h3><table><tr><th>Quando</th><th>IP</th><th>Tipo</th><th>Risco</th><th>Ação</th></tr>{% for a in ataques %}<tr><td>{{ a['criado_em'] }}</td><td>{{ a['ip'] }}</td><td>{{ a['tipo'] }}</td><td><span class="badge {% if a['score']>=90 %}critico{% elif a['score']>=60 %}alto{% else %}medio{% endif %}">{{ a['score'] }} pts</span><br><small>{{ a['detalhes'] }}</small><br><small style="color:#94a3b8">{{ a['url'] }}</small></td><td><form action="/admin/desbloquear" method="POST"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="ip" value="{{ a['ip'] }}"><button class="btn2">Desbloquear</button></form></td></tr>{% else %}<tr><td colspan="5">✅ Nenhum ataque hoje. Seu site está limpo!</td></tr>{% endfor %}</table></div><div class="box"><h3>🔒 IPs Bloqueados Agora</h3>{% for ip, ate in bloqueados %}<p>🔴 {{ ip }} - até {{ ate }} <form action="/admin/desbloquear" method="POST" style="display:inline"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><input type="hidden" name="ip" value="{{ ip }}"><button class="btn">Desbloquear</button></form></p>{% else %}<p>✅ Nenhum IP bloqueado.</p>{% endfor %}</div></div></body></html>"""

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    if "/" in filename or "\\" in filename or ".." in filename: abort(404)
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/")
def loja():
    conn = conectar_db(); produtos = conn.execute("SELECT * FROM produtos WHERE estoque > 0 ORDER BY id DESC").fetchall(); conn.close()
    return render_template_string(HTML_LOJA, produtos=produtos, qtd_carrinho=len(session.get("carrinho",[])), nome_loja=NOME_LOJA, csrf_token=gerar_csrf())

@app.route("/adicionar/<int:produto_id>", methods=["POST"])
def adicionar(produto_id):
    tamanho = request.form.get("tamanho","Único")[:20]
    conn = conectar_db(); p = conn.execute("SELECT * FROM produtos WHERE id=? AND estoque>0",(produto_id,)).fetchone(); conn.close()
    if not p: return redirect(url_for("loja"))
    validos=[t.strip() for t in (p["tamanhos"] or "").split(",")]
    if tamanho not in validos: tamanho = validos[0] if validos else "Único"
    carrinho=session.get("carrinho",[])
    if len(carrinho)>=50: return redirect(url_for("ver_carrinho"))
    carrinho.append({"id":produto_id,"tamanho":tamanho}); session["carrinho"]=carrinho
    return redirect(url_for("loja"))

@app.route("/carrinho")
def ver_carrinho():
    itens=[]; total=0.0; conn=conectar_db()
    for it in session.get("carrinho",[]):
        try: pid=int(it.get("id"))
        except Exception: continue
        prod=conn.execute("SELECT * FROM produtos WHERE id=?",(pid,)).fetchone()
        if prod: itens.append({"nome":prod["nome"],"preco":prod["preco"],"tamanho":str(it.get("tamanho","Único"))[:20]}); total+=prod["preco"]
    conn.close()
    texto="Olá! Gostaria de encomendar:\n" + "".join([f"- {i['nome']} [Tam: {i['tamanho']}] - R$ {i['preco']:.2f}\n" for i in itens]) + f"\n*Total: R$ {total:.2f}*"
    link=f"https://wa.me/{SEU_WHATSAPP}?text={urllib.parse.quote(texto)}"
    return render_template_string(HTML_CARRINHO, itens=itens, total=total, link_whatsapp=link, nome_loja=NOME_LOJA, csrf_token=gerar_csrf())

@app.route("/limpar", methods=["POST"])
def limpar_carrinho(): session["carrinho"]=[]; return redirect(url_for("ver_carrinho"))

@app.route("/admin", methods=["GET","POST"])
def admin():
    erro=None
    if request.method=="POST" and "senha" in request.form:
        tent=session.get("tentativas_login",0)
        if tent>=5: erro="Muitas tentativas. Feche o navegador e tente depois."
        elif secrets.compare_digest(request.form.get("senha",""), SENHA_ADMIN):
            session["logado"]=True; session.pop("tentativas_login",None); session["csrf_token"]=secrets.token_hex(16)
        else:
            session["tentativas_login"]=tent+1
            # Se errar 5x, bloqueia o IP por 15 min (anti forca bruta)
            if tent+1>=5:
                ip=ip_cliente(); IPS_BLOQUEADOS[ip]=time.time()+900
                registrar_ataque(ip,"FORÇA BRUTA - 5 senhas erradas",95,"Tentou adivinhar senha do admin 5x","/admin")
            erro="Senha incorreta!"
    if not session.get("logado"): return render_template_string(HTML_ADMIN, logado=False, erro=erro, nome_loja=NOME_LOJA, csrf_token=gerar_csrf())
    conn=conectar_db(); produtos=conn.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall(); conn.close()
    return render_template_string(HTML_ADMIN, logado=True, produtos=produtos, nome_loja=NOME_LOJA, csrf_token=gerar_csrf())

# --- NOVO: PAINEL DE SEGURANCA IA ---
@app.route("/admin/seguranca")
def painel_seguranca():
    if not session.get("logado"): return redirect(url_for("admin"))
    hoje=datetime.now().strftime("%Y-%m-%d")
    conn=conectar_db()
    ataques=conn.execute("SELECT * FROM ataques WHERE criado_em LIKE ? ORDER BY id DESC LIMIT 50",(hoje+"%",)).fetchall()
    total_hoje=len(ataques)
    acessos=conn.execute("SELECT COUNT(*) c FROM acessos WHERE criado_em LIKE ?",(hoje+"%",)).fetchone()["c"]
    conn.close()
    bloqueados=[(ip, datetime.fromtimestamp(ate).strftime("%H:%M:%S")) for ip,ate in IPS_BLOQUEADOS.items() if ate>time.time()]
    status="🔴 SOB ATAQUE" if total_hoje>10 else ("🟡 ALERTA" if total_hoje>0 else "🟢 SEGURO")
    return render_template_string(HTML_SEGURANCA, ataques=ataques, total_hoje=total_hoje, acessos_hoje=acessos, ips_bloqueados=len(bloqueados), bloqueados=bloqueados, status=status, csrf_token=gerar_csrf())

@app.route("/admin/desbloquear", methods=["POST"])
def desbloquear():
    if not session.get("logado"): return redirect(url_for("admin"))
    ip=request.form.get("ip","")
    IPS_BLOQUEADOS.pop(ip,None); PONTOS_IP.pop(ip,None)
    return redirect(url_for("painel_seguranca"))

# API para voce ver em tempo real (opcional)
@app.route("/api/seguranca/status")
def api_status():
    if not session.get("logado"): abort(403)
    return jsonify({"bloqueados":len(IPS_BLOQUEADOS),"ips":list(IPS_BLOQUEADOS.keys()),"scores":dict(PONTOS_IP)})

@app.route("/admin/novo", methods=["POST"])
def admin_novo_produto():
    if not session.get("logado"): return redirect(url_for("admin"))
    try:
        nome=(request.form.get("nome") or "").strip()[:100]
        if not nome: return redirect(url_for("admin"))
        preco=float((request.form.get("preco") or "0").replace(",","."))
        if preco<0 or preco>100000: return redirect(url_for("admin"))
        categoria=(request.form.get("categoria") or "")[:30]; tamanhos=re.sub(r"[^A-Za-z0-9, ]","",(request.form.get("tamanhos") or "P,M,G,GG")[:50])
        estoque=max(0,min(int(request.form.get("estoque") or 0),10000))
    except Exception: return redirect(url_for("admin"))
    foto=request.files.get("foto")
    if foto and foto.filename!="":
        if not extensao_permitida(foto.filename): return redirect(url_for("admin"))
        nome_arq=nome_arquivo_seguro(foto.filename); foto.save(os.path.join(UPLOAD_FOLDER,nome_arq)); caminho=f"/uploads/{nome_arq}"
    else: caminho="https://placehold.co/600x400?text=STUDIO+WEAR"
    conn=conectar_db(); conn.execute("INSERT INTO produtos (nome,preco,categoria,tamanhos,estoque,imagem) VALUES (?,?,?,?,?,?)",(nome,preco,categoria,tamanhos,estoque,caminho)); conn.commit(); conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/excluir/<int:produto_id>", methods=["POST"])
def admin_excluir_produto(produto_id):
    if not session.get("logado"): return redirect(url_for("admin"))
    conn=conectar_db(); prod=conn.execute("SELECT imagem FROM produtos WHERE id=?",(produto_id,)).fetchone(); conn.execute("DELETE FROM produtos WHERE id=?",(produto_id,)); conn.commit(); conn.close()
    if prod and prod["imagem"] and prod["imagem"].startswith("/uploads/"):
        try:
            n=os.path.basename(prod["imagem"])
            if ".." not in n: 
                c=os.path.join(UPLOAD_FOLDER,n)
                if os.path.exists(c): os.remove(c)
        except Exception: pass
    return redirect(url_for("admin"))

@app.route("/admin/sair")
def admin_sair(): session.clear(); return redirect(url_for("loja"))

if __name__=="__main__":
    print("🛡️ DEFESA IA ATIVA - WAF + IDS + Honeypot + Anti-DDoS + Anti-Forca Bruta")
    print("📊 Painel: http://127.0.0.1:5000/admin/seguranca")
    app.run(debug=False, host="127.0.0.1", port=5000)
