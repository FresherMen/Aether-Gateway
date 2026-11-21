import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

try:
    from .config import RAGConfig, default_config
except ImportError:
    from engine.config import RAGConfig, default_config


class LocalLLMClient:
    def __init__(self, config: RAGConfig = default_config):
        self.config = config

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.config.enable_api_fallback:
            return self._call_ollama(prompt, system_prompt)

        if self.config.fallback_provider == "gemini" and self.config.gemini_api_key:
            try:
                return self._call_gemini(prompt, system_prompt)
            except Exception:
                return self._call_ollama(prompt, system_prompt)

        return self._call_ollama(prompt, system_prompt)

    def _call_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        url = f"{self.config.ollama_base_url.rstrip('/')}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.config.local_model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except urllib.error.URLError:
            return self._offline_deterministic_fallback(prompt, system_prompt)

    def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        model = self.config.gemini_model_name
        api_key = self.config.gemini_api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTION: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly obey these constraints and cite official sources."}]})

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_tokens
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return self.config.strict_refusal_phrase

    def _offline_deterministic_fallback(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        prompt_lower = prompt.lower()
        for kw in self.config.injection_keywords:
            if kw in prompt_lower:
                return self.config.strict_refusal_phrase

        if "context:" not in prompt_lower or "question:" not in prompt_lower:
            return self.config.strict_refusal_phrase

        parts = prompt.split("Context:\n")
        subparts = parts[1].split("\n\nQuestion:")
        context_block = subparts[0].strip()
        question = subparts[1].split("\n\nAnswer:")[0].strip().lower()

        if not context_block or "not in the sources" in context_block.lower():
            return self.config.strict_refusal_phrase

        if "guarantee" in question or "promise" in question:
            disclaimer = "NEET.info provides historical statistical estimates and does not guarantee admission."
            return f"According to official counselling policy: {disclaimer}"

        sections = context_block.split("\nSection: ")
        best_section = None
        best_sec_overlap = 0
        q_tokens = set(question.replace("?", "").replace(",", "").split())

        for sec in sections:
            sec_clean = ("Section: " + sec) if not sec.startswith("Section: ") else sec
            sec_tokens = set(sec_clean.lower().replace(",", "").replace(".", "").split())
            overlap = len(q_tokens.intersection(sec_tokens))
            if overlap > best_sec_overlap:
                best_sec_overlap = overlap
                best_section = sec_clean

        if best_section and best_sec_overlap >= 3:
            first_lines = "\n".join(best_section.strip().split("\n")[:5])
            return f"Based on official sources: {first_lines}"

        context_lines = [line.strip() for line in context_block.split("\n") if line.strip()]
        best_match = None
        best_overlap = 0

        for line in context_lines:
            line_tokens = set(line.lower().replace(",", "").replace(".", "").split())
            overlap = len(q_tokens.intersection(line_tokens))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = line

        if best_match and best_overlap >= 3:
            return f"Based on the official sources: {best_match}"

        return self.config.strict_refusal_phrase
