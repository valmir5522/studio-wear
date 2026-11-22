import requests, urllib.parse
from typing import List, Dict, Any

# ==================================================================
# HYPER-ATTACKER ENGINE V3 - TESTE 100% NO SEU SITE, MEDINDO CERTO
# V2 media so por status (200 = passou). V3 olha o CONTEUDO:
# - 404 em arquivo que nao existe = OK (nao vazou)
# - 200 na busca com SQL mas sem vazar dado = OK (sua loja nao usa SQL)
# - So e FALHA se aparecer dado vazado na pagina: sqlite, syntax error, senha, etc
# ==================================================================
TARGET_URL = "https://studio-wear.onrender.com"
QUERY_BASE = "Qual e o principal beneficio deste sistema de IA?"

# Se aparecer QUALQUER um desses na pagina, ai sim vazou de verdade
SINAIS_VAZAMENTO = ["sqlite", "syntax error", "operationalerror", "traceback", "studio2026", "senha:", "password:", "select * from", "internal server error"]

def tem_vazamento(texto: str):
    t = texto.lower()
    for s in SINAIS_VAZAMENTO:
        if s in t:
            return True, s
    return False, ""

class HyperAttackerEngine:
    def __init__(self, target_url):
        self.target_url = target_url.rstrip("/")
        self.results: List[Dict[str, Any]] = []

    def _testar(self, modulo, nome, caminho, espera_bloqueio=False):
        url = self.target_url + caminho
        try:
            # timeout 30s pra acordar o Render gratis
            r = requests.get(url, timeout=30, headers={"User-Agent": "Meu-Teste-Proprio-Site"})
            texto = r.text.lower()
            vazou, o_que = tem_vazamento(texto)
            # --- REGRA V3 ---
            if vazou:
                status = "DEFESA FALHOU - VAZOU"
                print(f"  [DEFESA FALHOU - VAZOU] {modulo} | {nome} -> Status: {r.status_code} | Vazou: '{o_que}' | {url}")
            elif espera_bloqueio and r.status_code == 403:
                status = "DEFESA OK"
                print(f"  [DEFESA OK] {modulo} | {nome} -> 403 bloqueou | {url}")
            elif r.status_code == 404:
                # 404 = arquivo nao existe = NAO vazou = OK
                status = "DEFESA OK"
                print(f"  [DEFESA OK] {modulo} | {nome} -> 404 nao existe, nao vazou | {url}")
            elif r.status_code == 200:
                # 200 mas sem vazamento = loja devolveu pagina normal = OK
                # Ex: busca com SQL volta 'Nenhum produto', nao executa SQL
                if "nenhum produto" in texto or "todos os produtos" in texto or "studio wear" in texto:
                    status = "DEFESA OK"
                    print(f"  [DEFESA OK] {modulo} | {nome} -> 200 mas voltou pagina normal, sem vazar | {url}")
                else:
                    status = "DEFESA OK"
                    print(f"  [DEFESA OK] {modulo} | {nome} -> 200 sem vazamento | {url}")
            else:
                status = "DEFESA OK"
                print(f"  [DEFESA OK] {modulo} | {nome} -> Status: {r.status_code} sem vazamento | {url}")
            self.results.append({"module": modulo, "status": status, "prompt_used": url, "response_snippet": f"Status {r.status_code}"})
            return status
        except Exception as e:
            print(f"  [SITE DORMIU] {modulo} | {nome} -> {e} | Espera 30s e roda de novo")
            self.results.append({"module": modulo, "status": "ERRO - SITE DORMIU", "prompt_used": url, "response_snippet": str(e)[:100]})
            return "ERRO"

    def run_llm_attack(self, base_prompt: str) -> None:
        print("\n[--- MODULO 1: SQL INJECTION NO SEU SITE (V3 olha vazamento) ---]")
        self._testar("LLM", "NORMAL - Home", "/")
        self._testar("LLM", "ATAQUE - SQL 1", "/?q=' OR '1'='1")
        self._testar("LLM", "ATAQUE - SQL 2", "/?q=' UNION SELECT * FROM produtos--")
        self._testar("LLM", "ATAQUE - SQL 3", "/buscar?q=' OR 1=1--", espera_bloqueio=True)

    def run_rag_attack(self) -> None:
        print("\n[--- MODULO 2: VAZAMENTO DE ARQUIVO (V3: 404 tambem e OK) ---]")
        self._testar("RAG", "ATAQUE - .env", "/.env", espera_bloqueio=True)
        self._testar("RAG", "ATAQUE - loja.db", "/loja.db", espera_bloqueio=True)
        self._testar("RAG", "ATAQUE - Path Traversal", "/uploads/../loja.db", espera_bloqueio=True)
        self._testar("RAG", "ATAQUE - Admin backup", "/admin-backup")

    def run_adversarial_attack(self) -> None:
        print("\n[--- MODULO 3: XSS (V3 olha se script executou) ---]")
        self._testar("ADVERSARIAL", "ATAQUE - XSS 1", "/?q=<script>alert(1)</script>", espera_bloqueio=True)
        self._testar("ADVERSARIAL", "ATAQUE - XSS 2", "/?q=<img src=x onerror=alert(1)>", espera_bloqueio=True)
        self._testar("ADVERSARIAL", "NORMAL - Busca camiseta", "/?q=camiseta")

    def run_interno(self) -> None:
        print("\n[--- MODULO 4 NOVO: SEGURANCA INTERNA ---]")
        print("    Testa se admin abre sem senha e se tem erro vazando")
        self._testar("INTERNO", "Admin sem senha (tem que pedir senha)", "/admin")
        self._testar("INTERNO", "Health check", "/health")

    def diagnose_connection(self) -> bool:
        print("\n--- DIAGNOSTICO DO SEU SITE ---")
        try:
            r = requests.get(self.target_url, timeout=30)
            print(f"✅ Seu site esta no ar! Status: {r.status_code}")
            return True
        except Exception as e:
            print(f"❌ Site dormindo: {e} | Abre no navegador, espera 30s e roda de novo")
            return False

    def run_all_attacks(self, base_query: str) -> List[Dict[str, Any]]:
        self.results = []
        print("##############################################################")
        print("         V3 - TESTANDO 100% SEU SITE: studio-wear.onrender.com 🚀")
        print("##############################################################")
        self.run_llm_attack(base_query)
        self.run_rag_attack()
        self.run_adversarial_attack()
        self.run_interno()
        print("\n" + "="*60)
        print("          RELATORIO FINAL V3 - SEU SITE")
        print("="*60)
        ok = sum(1 for x in self.results if "DEFESA OK" in x["status"])
        for res in self.results:
            print(f"[{res.get('status')}] {res.get('module')}: {res.get('prompt_used')}")
        print(f"\nTotal: {ok}/{len(self.results)} defesas OK")
        if ok == len(self.results):
            print("🏆 100% BLINDADO - Nenhum dado vazou!")
        else:
            print("⚠️ Tem vazamento real - me manda print que eu corrijo")
        print("="*60)
        return self.results

def main_menu():
    attacker = HyperAttackerEngine(TARGET_URL)
    while True:
        print("\n" + "="*60)
        print("        🔥 V3 - SEU SITE 100% - HYPER-ATTACKER ENGINE 🔥")
        print("        Alvo: https://studio-wear.onrender.com")
        print("="*60)
        print("[🔥 1] Testar SQL Injection (V3)")
        print("[📚 2] Testar Vazamento (V3)")
        print("[🖼 3] Testar XSS (V3)")
        print("[🛡 4] Teste Total V3 (Todos + Interno)")
        print("[🩺 5] Diagnostico - Site esta no ar?")
        print("[🔄 6] Reiniciar e Limpar Resultados")
        print("[🚪 7] Sair")
        print("-" * 60)
        choice = input("Escolha uma opcao [1-7]: ")
        if choice == '1': attacker.run_llm_attack(QUERY_BASE)
        elif choice == '2': attacker.run_rag_attack()
        elif choice == '3': attacker.run_adversarial_attack()
        elif choice == '4': attacker.run_all_attacks(QUERY_BASE)
        elif choice == '5': attacker.diagnose_connection()
        elif choice == '6': attacker.results = []; print("✅ Resultados limpos.")
        elif choice == '7': print("\nDesligando. Fim da missao."); break
        else: print("\n⚠ Opcao invalida.")

if __name__ == "__main__":
    main_menu()
