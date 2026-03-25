"""
src/extract/llm_normalizer.py
=============================
Normalização de trechos de manuais via LLM — suporte multi-provedor.

Provedores suportados (configurável via LLM_PROVIDER no .env):
    1. Anthropic Claude  (LLM_PROVIDER=anthropic)  — recomendado para extração estruturada
    2. OpenAI GPT        (LLM_PROVIDER=openai)      — JSON mode nativo
    3. Google Gemini     (LLM_PROVIDER=gemini)      — custo baixo, suporte a PDF nativo
    4. Ollama (local)    (LLM_PROVIDER=ollama)      — zero custo, privacidade total

Configuração via .env:
    LLM_PROVIDER=anthropic
    ANTHROPIC_API_KEY=sk-ant-...
    ANTHROPIC_MODEL=claude-sonnet-4-20250514

    # OU: OpenAI
    LLM_PROVIDER=openai
    OPENAI_API_KEY=sk-...
    OPENAI_MODEL=gpt-4.1-mini

    # OU: Google Gemini
    LLM_PROVIDER=gemini
    GOOGLE_API_KEY=...
    GEMINI_MODEL=gemini-1.5-flash

    # OU: Ollama local
    LLM_PROVIDER=ollama
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_MODEL=llama3.1

    ENABLE_LLM_NORMALIZATION=true
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é um especialista em taxas de intercâmbio de cartões de pagamento no Brasil.

Analise trechos de manuais técnicos das Bandeiras (Visa, Mastercard, Amex, Elo, Hipercard)
e converta cada trecho em uma lista JSON de regras de intercâmbio.

Para cada regra, retorne um objeto com:
- rule_type: "base_rate"|"merchant_adjustment"|"installment_adjustment"|"contactless_adjustment"|"cnp_adjustment"|"cnp_authenticated_adjustment"|"fixed_fee"|"cap"|"floor"|"regulatory_cap"
- audience: "PF"|"PJ"|"ALL" ou null
- card_family: "credit"|"debit"|"prepaid"|"cash_withdrawal" ou null
- product: nome exato (ex: "Platinum", "Centurion") ou null
- merchant_group: segmento (ex: "supermercados") ou null
- channel: "cp"|"cp_contactless"|"cnp"|"atm" ou null
- installment_band: "2-6"|"7-12"|"7-21"|"avista" ou null
- rate_pct: número decimal (ex: 1.73) ou null
- fixed_fee_amount: número BRL (ex: 8.0) ou null
- cap_amount: número BRL (ex: 0.35) ou null
- evidence_text: trecho que gerou a regra (max 200 chars)

NUNCA invente valores. Use null quando não há evidência.
Responda APENAS com JSON: {"rules": [{...}]}"""


def normalize_with_llm(snippet: str) -> list[dict[str, Any]]:
    """Normaliza um trecho via LLM configurado. Retorna [] se desabilitado."""
    if not settings.enable_llm_normalization:
        return []
    if len(snippet.strip()) < 20:
        return []

    provider = getattr(settings, "llm_provider", "anthropic").lower()

    try:
        if provider == "anthropic" and getattr(settings, "anthropic_api_key", None):
            return _call_anthropic(snippet)
        elif provider == "openai" and getattr(settings, "openai_api_key", None):
            return _call_openai(snippet)
        elif provider == "gemini" and getattr(settings, "google_api_key", None):
            return _call_gemini(snippet)
        elif provider == "ollama":
            return _call_ollama(snippet)
        else:
            # Auto-detect
            if getattr(settings, "anthropic_api_key", None):
                return _call_anthropic(snippet)
            elif getattr(settings, "openai_api_key", None):
                return _call_openai(snippet)
            elif getattr(settings, "google_api_key", None):
                return _call_gemini(snippet)
            else:
                logger.warning("Nenhuma API key LLM configurada. Defina ANTHROPIC_API_KEY, OPENAI_API_KEY ou GOOGLE_API_KEY.")
                return []
    except Exception as exc:
        logger.warning("Erro LLM (%s): %s", provider, exc)
        return []


def _parse_llm_response(text: str) -> list[dict[str, Any]]:
    """Extrai JSON da resposta do LLM, tolerando markdown code blocks."""
    clean = text.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif clean.startswith("```"):
        clean = "\n".join(clean.split("\n")[1:]).strip()
        if clean.endswith("```"):
            clean = "\n".join(clean.split("\n")[:-1]).strip()
    try:
        parsed = json.loads(clean)
        rules = parsed.get("rules", [])
        logger.info("LLM extraiu %d regras.", len(rules))
        return rules
    except json.JSONDecodeError as e:
        logger.warning("JSON inválido na resposta LLM: %s | texto: %s", e, clean[:200])
        return []


def _call_anthropic(snippet: str) -> list[dict[str, Any]]:
    """Anthropic Claude API."""
    import httpx
    model = getattr(settings, "anthropic_model", "claude-sonnet-4-20250514")
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        json={"model": model, "max_tokens": 1024, "system": SYSTEM_PROMPT,
              "messages": [{"role": "user", "content": snippet}], "temperature": 0},
        headers={"x-api-key": settings.anthropic_api_key,
                 "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
        timeout=90.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    logger.debug("Anthropic: model=%s", model)
    return _parse_llm_response(text)


def _call_openai(snippet: str) -> list[dict[str, Any]]:
    """OpenAI API (compatível com Azure e proxies OpenAI-like)."""
    import httpx
    api_key = getattr(settings, "openai_api_key", "")
    base_url = getattr(settings, "openai_base_url", "https://api.openai.com/v1")
    model = getattr(settings, "openai_model", "gpt-4.1-mini")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json={"model": model, "temperature": 0, "max_tokens": 1024,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": snippet}]},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=90.0,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    logger.debug("OpenAI: model=%s", model)
    return _parse_llm_response(text)


def _call_gemini(snippet: str) -> list[dict[str, Any]]:
    """Google Gemini API."""
    import httpx
    api_key = getattr(settings, "google_api_key", "")
    model = getattr(settings, "gemini_model", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    resp = httpx.post(
        url,
        json={"contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\nTexto:\n{snippet}"}]}],
              "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
        timeout=90.0,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    logger.debug("Gemini: model=%s", model)
    return _parse_llm_response(text)


def _call_ollama(snippet: str) -> list[dict[str, Any]]:
    """Ollama local (zero custo). Requer: ollama serve && ollama pull llama3.1"""
    import httpx
    base_url = getattr(settings, "ollama_base_url", "http://localhost:11434")
    model = getattr(settings, "ollama_model", "llama3.1")
    resp = httpx.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
              "prompt": f"{SYSTEM_PROMPT}\n\nTexto a analisar:\n{snippet}"},
        timeout=120.0,
    )
    resp.raise_for_status()
    text = resp.json().get("response", "{}")
    logger.debug("Ollama: model=%s url=%s", model, base_url)
    return _parse_llm_response(text)


def normalize_batch(snippets: list[str], max_per_call: int = 3) -> list[dict[str, Any]]:
    """Normaliza múltiplos snippets em batch, reduzindo chamadas à API."""
    all_rules: list[dict[str, Any]] = []
    sep = "\n\n--- PRÓXIMO TRECHO ---\n\n"
    for i in range(0, len(snippets), max_per_call):
        batch = snippets[i: i + max_per_call]
        rules = normalize_with_llm(sep.join(batch))
        all_rules.extend(rules)
    return all_rules
