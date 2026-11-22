# loja_com_defesa_ia.py - LOJA STUDIO WEAR COMPLETA + DEFESA CORRIGIDA
# Defesa bloqueia SO ataque de verdade. Cliente normal (home, busca camiseta) passa.
# Senha do admin vem do Render: ADMIN_PASSWORD (nao deixa senha no codigo)
import os
from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "studio-wear-secreta-troque-isso")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Studio2026!")

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
def defesa():
    # 1. Deixa passar arquivos estaticos e health check do Render
    if request.path.startswith("/static") or request.path == "/health":
        return None
    # LAB DE TESTE: deixa passar TODAS as rotas /lab- pra voce estudar
    if request.path.startswith("/lab-"):
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
    html = HTML_BASE.replace("{{conteudo}}", conteudo).replace("{{q}}", q).replace("{{carrinho_len}}", str(len(carrinho)))
    return render_template_string(html)

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


@app.route("/lab-vulneravel")
def lab_vulneravel():
    # ROTA DE LAB - DE MENTIRINHA, SO PRA TESTE NO SEU SITE
    # Simula uma busca vulneravel: se vier UNION SELECT, devolve o dado fake
    q = request.args.get("q", "")
    if "union select" in q.lower():
        return render("<div class='card'><h2>💡 LAB - BRECHA ACHADA!</h2><p>Voce conseguiu acessar a parte do LAB!</p><p><b>PRODUTO_SECRETO_FAKE_123</b></p><p>Isso e FALSO, so pra voce aprender como um ataque funciona.</p><a class='btn' href='/'>Voltar pra loja</a></div>")
    return render("<div class='card'><h2>LAB Vulneravel - Teste</h2><p>Essa pagina e de proposito vulneravel, so pra teste no seu site.</p><p>Tente: ?q=UNION SELECT</p><a class='btn' href='/'>Voltar pra loja</a></div>")


# ==================================================================
# LABORATORIO COMPLETO - SO DADO FAKE, SO NO SEU SITE
# ==================================================================
DADOS_FAKE_LAB = {
    "sqli": "FLAG_FAKE_SQLI_123",
    "xss": "FLAG_FAKE_XSS_456",
    "arquivo": "FLAG_FAKE_ARQUIVO_789",
    "login": "FLAG_FAKE_LOGIN_000",
}

@app.route("/lab")
def lab_home():
    return render("""<h2>🧪 Laboratorio Completo - STUDIO WEAR</h2>
    <div class='card'><p>Lab so pra estudo, no seu proprio site. Tudo aqui e FAKE.</p>
    <p><b>Fase 1:</b> <a href='/lab-sqli'>/lab-sqli</a> - Achar brecha SQLi</p>
    <p><b>Fase 2:</b> <a href='/lab-xss'>/lab-xss</a> - Achar brecha XSS</p>
    <p><b>Fase 3:</b> <a href='/lab-arquivo'>/lab-arquivo</a> - Achar vazamento de arquivo</p>
    <p><b>Fase 4:</b> <a href='/lab-login'>/lab-login</a> - Achar brecha de login</p>
    <p><b>Fase 5:</b> Corrigir tudo e ver o painel de defesa</p>
    </div><a class='btn' href='/'>Voltar pra loja</a>""")

@app.route("/lab-sqli")
def lab_sqli():
    q = request.args.get("q", "")
    # FASE 1: se vier UNION SELECT, mostra a flag fake
    if "union select" in q.lower():
        return render(f"<div class='card'><h2>💡 FASE 1 CONCLUIDA - SQLi!</h2><p>Voce achou a brecha do SQLi.</p><p><b>{DADOS_FAKE_LAB['sqli']}</b></p><p>Anota essa flag e vai pra Fase 2.</p><a class='btn' href='/lab'>Voltar pro LAB</a></div>")
    return render("""<div class='card'><h2>Fase 1 - SQLi</h2><p>Busca normal aqui. Tente achar o que faz vazar a flag.</p>
    <form action='/lab-sqli' method='get'><input name='q' placeholder='Tente: camiseta'><button>Buscar</button></form>
    <p>Dica: a loja normal filtra em memoria e NAO vaza. O LAB simula o que uma loja vulneravel faria.</p></div><a class='btn' href='/lab'>Voltar pro LAB</a>""")

@app.route("/lab-xss")
def lab_xss():
    q = request.args.get("q", "")
    if "<script" in q.lower() or "alert(" in q.lower():
        return render(f"<div class='card'><h2>💡 FASE 2 CONCLUIDA - XSS!</h2><p>Voce achou a brecha de XSS.</p><p><b>{DADOS_FAKE_LAB['xss']}</b></p><a class='btn' href='/lab'>Voltar pro LAB</a></div>")
    return render("""<div class='card'><h2>Fase 2 - XSS</h2><p>O que voce digitar aqui aparece na tela sem filtro (so no LAB).</p>
    <form action='/lab-xss' method='get'><input name='q' placeholder='Digite algo'><button>Testar</button></form></div><a class='btn' href='/lab'>Voltar pro LAB</a>""")

@app.route("/lab-arquivo")
def lab_arquivo():
    f = request.args.get("f", "")
    if ".env" in f or "loja.db" in f or "../" in f:
        return render(f"<div class='card'><h2>💡 FASE 3 CONCLUIDA - Vazamento de arquivo!</h2><p>Voce tentou acessar arquivo proibido e o LAB mostrou a flag.</p><p><b>{DADOS_FAKE_LAB['arquivo']}</b></p><a class='btn' href='/lab'>Voltar pro LAB</a></div>")
    return render("""<div class='card'><h2>Fase 3 - Vazamento de arquivo</h2><p>Parametro ?f= nome do arquivo</p>
    <p>Exemplo normal: <a href='/lab-arquivo?f=produto.txt'>?f=produto.txt</a></p>
    <p>Tente acessar algo que nao deveria.</p></div><a class='btn' href='/lab'>Voltar pro LAB</a>""")

@app.route("/lab-login", methods=["GET", "POST"])
def lab_login():
    if request.method == "POST":
        u = request.form.get("usuario", "")
        s = request.form.get("senha", "")
        # FASE 4: login fake vulneravel - ' OR '1'='1 entra
        if "' or '1'='1" in (u + s).lower() or "' or 1=1" in (u + s).lower():
            return render(f"<div class='card'><h2>💡 FASE 4 CONCLUIDA - Login bypass!</h2><p>Voce entrou sem saber a senha, usando SQLi no login.</p><p><b>{DADOS_FAKE_LAB['login']}</b></p><a class='btn' href='/lab'>Voltar pro LAB</a></div>")
        return render("<div class='card'><b>Login errado no LAB.</b></div><a class='btn' href='/lab-login'>Tentar de novo</a>")
    return render("""<h2>Fase 4 - Login</h2><div class='card'><form method='post'>
    <input name='usuario' placeholder='Usuario'><br><br>
    <input name='senha' placeholder='Senha'><br><br><button>Entrar</button></form>
    <p>Dica: no LAB, a senha fake nao e o objetivo - o objetivo e entrar SEM a senha.</p></div><a class='btn' href='/lab'>Voltar pro LAB</a>""")

@app.route("/lab-vulneravel")
def lab_vulneravel_old():
    # Mantem compatibilidade com o teste antigo
    return redirect("/lab-sqli")

@app.errorhandler(404)
def erro404(e):
    return render("<div class='card'><h2>Pagina nao encontrada (404)</h2><a class='btn' href='/'>Voltar pra loja</a></div>"), 404

@app.errorhandler(403)
def erro403(e):
    return "Bloqueado pela defesa - tentativa de ataque detectada.", 403

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
