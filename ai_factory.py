"""
AI FACTORY -- Orquestrador Gemini + Claude
  Arquiteto: Google Gemini 1.5 Pro  |  Executor: Claude Code CLI

Fluxo:
  1. Usuario descreve a tarefa
  2. Gemini gera um plano detalhado -> PLANO_DE_ACAO.md
  3. Claude Code CLI le o plano e executa passo a passo nos arquivos reais
"""

import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

# Força UTF-8 no stdout para evitar UnicodeEncodeError no Windows (cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# Paleta de cores ANSI para terminal
# ──────────────────────────────────────────────
class Cor:
    RESET   = "\033[0m"
    NEGRITO = "\033[1m"
    # Agentes
    GEMINI  = "\033[94m"   # Azul brilhante  → Arquiteto Gemini
    CLAUDE  = "\033[92m"   # Verde brilhante → Executor Claude
    SISTEMA = "\033[95m"   # Magenta         → Sistema/Orquestrador
    AVISO   = "\033[93m"   # Amarelo         → Avisos
    ERRO    = "\033[91m"   # Vermelho        → Erros
    INFO    = "\033[96m"   # Ciano           → Informações gerais


def banner():
    """Exibe o banner inicial do orquestrador."""
    print(f"""
{Cor.SISTEMA}{Cor.NEGRITO}
+==================================================================+
|          [*] AI FACTORY -- Orquestrador Dual-Agent [*]           |
|                                                                  |
|   [A] ARQUITETO : Google Gemini 1.5 Pro                          |
|   [E] EXECUTOR  : Claude Code CLI (local)                        |
+==================================================================+
{Cor.RESET}""")


def log(agente: str, mensagem: str, cor: str = Cor.INFO):
    """Imprime uma linha de log formatada com identificação do agente."""
    print(f"{cor}{Cor.NEGRITO}[{agente}]{Cor.RESET}{cor} {mensagem}{Cor.RESET}")


# ──────────────────────────────────────────────
# Carregamento das variáveis de ambiente
# ──────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PLANO_PATH = Path("PLANO_DE_ACAO.md")

PROMPT_SISTEMA_ARQUITETO = """
Você é um Arquiteto de Software Sênior especializado em sistemas industriais, MLOps e automação.
Sua única responsabilidade é analisar a solicitação do usuário e produzir um plano de ação
técnico, detalhado e executável.

REGRAS OBRIGATÓRIAS:
1. Produza APENAS o plano em Markdown. Nenhuma introdução ou conclusão fora do plano.
2. O plano deve conter seções: ## Objetivo, ## Contexto, ## Passo a Passo, ## Testes Esperados.
3. Cada passo do "Passo a Passo" deve ter:
   - Número do passo
   - Arquivo(s) afetado(s) (caminho relativo à raiz do projeto)
   - Ação exata a realizar (criar, modificar, deletar)
   - Trecho de código ou instrução precisa
4. A seção "Testes Esperados" deve listar comandos reais para validar o resultado.
5. Seja cirúrgico e não quebre funcionalidades existentes.
6. Nunca sugira deletar arquivos críticos sem backup explícito no plano.
"""


# ──────────────────────────────────────────────
# AGENTE 1: Gemini como Arquiteto
# ──────────────────────────────────────────────
def gerar_plano(solicitacao: str) -> bool:
    """
    Chama a API do Gemini 1.5 Pro com o prompt de Arquiteto.
    Salva o plano gerado em PLANO_DE_ACAO.md.
    Retorna True em caso de sucesso, False caso contrário.
    """
    log("GEMINI ARQUITETO", "[A] Iniciando geracao do plano de acao...", Cor.GEMINI)

    if not GEMINI_API_KEY:
        log("SISTEMA", "[!] GEMINI_API_KEY nao encontrada no .env!", Cor.ERRO)
        log("SISTEMA", "    Copie .env.example para .env e preencha a chave.", Cor.AVISO)
        return False

    try:
        import google.generativeai as genai  # import lazy -- so falha aqui se nao instalado
    except ImportError:
        log("SISTEMA", "[!] Pacote 'google-generativeai' nao instalado.", Cor.ERRO)
        log("SISTEMA", "    Execute: pip install -r requirements.txt", Cor.AVISO)
        return False

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        modelo = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=PROMPT_SISTEMA_ARQUITETO,
        )

        log("GEMINI ARQUITETO", "[>>] Enviando solicitacao ao modelo gemini-1.5-pro...", Cor.GEMINI)

        resposta = modelo.generate_content(solicitacao)
        plano_md = resposta.text

        PLANO_PATH.write_text(plano_md, encoding="utf-8")

        log("GEMINI ARQUITETO", f"[OK] Plano salvo em: {PLANO_PATH.resolve()}", Cor.GEMINI)
        log("GEMINI ARQUITETO", f"     ({len(plano_md.splitlines())} linhas geradas)", Cor.GEMINI)
        return True

    except Exception as exc:
        log("GEMINI ARQUITETO", f"[!!] Erro ao chamar a API do Gemini: {exc}", Cor.ERRO)
        return False


# ──────────────────────────────────────────────
# AGENTE 2: Claude Code CLI como Executor
# ──────────────────────────────────────────────
def executar_claude() -> bool:
    """
    Abre a CLI do Claude Code via subprocess e passa o comando de execução do plano.
    O Claude lê PLANO_DE_ACAO.md e executa as modificações nos arquivos reais.
    Retorna True se o processo terminar com código 0, False caso contrário.
    """
    log("CLAUDE EXECUTOR", "[E] Iniciando Claude Code CLI...", Cor.CLAUDE)

    if not PLANO_PATH.exists():
        log("SISTEMA", f"[!] Arquivo {PLANO_PATH} nao encontrado. Execute gerar_plano() primeiro.", Cor.ERRO)
        return False

    instrucao = (
        f"Leia o arquivo {PLANO_PATH.name} localizado na raiz do projeto. "
        "Execute cada passo descrito no plano de forma sequencial. "
        "Modifique os arquivos necessarios conforme instruido. "
        "Ao final, rode os testes listados na secao 'Testes Esperados' e reporte o resultado."
    )

    log("CLAUDE EXECUTOR", "[>>] Instrucao enviada ao Claude:", Cor.CLAUDE)
    log("CLAUDE EXECUTOR", f"     \"{instrucao}\"", Cor.CLAUDE)
    log("CLAUDE EXECUTOR", "[~~] Aguarde -- o Claude esta trabalhando...", Cor.CLAUDE)

    try:
        # Usa 'claude' da CLI instalada globalmente (npm install -g @anthropic-ai/claude-code)
        resultado = subprocess.run(
            ["claude", instrucao],
            check=False,           # não lança exceção em código != 0; tratamos manualmente
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if resultado.returncode == 0:
            log("CLAUDE EXECUTOR", "[OK] Claude finalizou a execucao com sucesso.", Cor.CLAUDE)
            return True
        else:
            log("CLAUDE EXECUTOR", f"[!]  Claude encerrou com codigo {resultado.returncode}.", Cor.AVISO)
            log("CLAUDE EXECUTOR", "     Verifique o terminal acima para detalhes.", Cor.AVISO)
            return False

    except FileNotFoundError:
        log("CLAUDE EXECUTOR", "[!] Comando 'claude' nao encontrado no PATH.", Cor.ERRO)
        log("SISTEMA", "    Instale o Claude Code CLI:", Cor.AVISO)
        log("SISTEMA", "    npm install -g @anthropic-ai/claude-code", Cor.AVISO)
        log("SISTEMA", "    Depois autentique: claude login", Cor.AVISO)
        return False

    except Exception as exc:
        log("CLAUDE EXECUTOR", f"[!!] Erro inesperado ao executar Claude: {exc}", Cor.ERRO)
        return False


# ──────────────────────────────────────────────
# Bloco principal interativo
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Habilita cores ANSI no Windows (PowerShell / cmd modernos)
    if sys.platform == "win32":
        os.system("")  # activa o modo VT100 no Windows Terminal

    banner()

    log("SISTEMA", "[*] Bem-vindo ao AI Factory -- Orquestrador Gemini + Claude", Cor.SISTEMA)
    log("SISTEMA", "    O Gemini vai PLANEJAR. O Claude vai EXECUTAR.", Cor.SISTEMA)
    print()

    # ── Entrada do usuário ──
    print(f"{Cor.INFO}Descreva a tarefa que deseja realizar no projeto:{Cor.RESET}")
    print(f"{Cor.AVISO}(Seja específico: mencione arquivos, funcionalidades, tecnologias){Cor.RESET}")
    print()

    try:
        solicitacao = input(f"{Cor.NEGRITO}> {Cor.RESET}").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        log("SISTEMA", "[!] Operacao cancelada pelo usuario.", Cor.AVISO)
        sys.exit(0)

    if not solicitacao:
        log("SISTEMA", "[!] Nenhuma solicitacao informada. Encerrando.", Cor.ERRO)
        sys.exit(1)

    print()
    log("SISTEMA", "-" * 60, Cor.SISTEMA)

    # ── Fase 1: Gemini gera o plano ──
    sucesso_plano = gerar_plano(solicitacao)

    if not sucesso_plano:
        log("SISTEMA", "[!!] Falha na geracao do plano. Fluxo interrompido.", Cor.ERRO)
        sys.exit(1)

    print()
    log("SISTEMA", "-" * 60, Cor.SISTEMA)

    # ── Fase 2: Claude executa o plano ──
    sucesso_exec = executar_claude()

    print()
    log("SISTEMA", "-" * 60, Cor.SISTEMA)

    # ── Resumo final ──
    if sucesso_plano and sucesso_exec:
        log("SISTEMA", "[OK] Fluxo completo finalizado com sucesso!", Cor.SISTEMA)
        log("SISTEMA", f"     Plano gerado: {PLANO_PATH.resolve()}", Cor.SISTEMA)
    else:
        log("SISTEMA", "[!]  Fluxo concluido com avisos. Revise os logs acima.", Cor.AVISO)

    print()
