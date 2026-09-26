"""AI-relevance classification.

The competition is about *AI* security, so collecting the whole of NVD would
bury the signal.  Every candidate is classified before it is stored and the
decision is recorded as a reason string on the event.

Deliberate conservatism:

* A single generic word such as "model" never qualifies an item on its own.
  Weak signals must corroborate each other, otherwise the corpus fills with
  unrelated CVEs that happen to contain the word.
* Anything that qualifies only on weak evidence is stored as `needs_review`
  rather than promoted to a confirmed AI-security event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Package or component names that are unambiguously AI infrastructure.
AI_PACKAGES: frozenset[str] = frozenset(
    {
        "ollama", "vllm", "triton", "tritonserver", "tensorrt", "onnxruntime", "onnx",
        "llamacpp", "llamafile", "textgenerationinference", "sglang", "lmdeploy",
        "openvino", "torchserve", "mlflow", "kubeflow", "pytorch", "torch", "tensorflow",
        "jax", "keras", "transformers", "huggingface", "diffusers", "accelerate", "peft",
        "sentence-transformers", "sentence_transformers", "langchain", "langgraph",
        "langserve", "llama-index", "llama_index", "llamaindex", "haystack", "autogen",
        "crewai", "dspy", "semantic-kernel", "semantic_kernel", "gradio", "open-webui",
        "openwebui", "comfyui", "automatic1111", "stable-diffusion-webui", "invokeai",
        "fooocus", "koboldcpp", "gpt4all", "text-generation-webui", "lmstudio",
        "faster-whisper", "whisperx", "openai", "anthropic", "mistral", "qwen", "deepseek",
        "vllm-project", "triton-inference-server", "milvus", "qdrant", "weaviate", "chroma",
        "faiss", "pgvector", "bentoml", "ray", "dask", "xgboost", "lightgbm", "catboost",
        "scikit-learn", "sklearn", "nvidia", "cuda", "cudnn", "nccl", "triton-inference",
        "deepsparse", "vllm_ascend", "mindspore", "paddlepaddle", "paddle", "modelscope",
        "llamafactory", "unsloth", "vllm-ascend", "xinference", "fastchat", "petals",
        "exllama", "exllamav2", "ctransformers", "optimum", "tgi", "tei", "dify", "flowise",
        "n8n", "langflow", "anythingllm", "localai", "jan", "msty", "llamafile-server",
    }
)

# Specific, unambiguous phrases.  Matching one is sufficient.
STRONG_TERMS: tuple[str, ...] = (
    "artificial intelligence", "large language model", "llm", "llms", "prompt injection", "jailbreak",
    "jailbreaking", "adversarial example", "adversarial patch", "model poisoning",
    "data poisoning", "training data poisoning", "model extraction", "model stealing",
    "membership inference", "model inversion", "system prompt", "prompt leak",
    "rag poisoning", "retrieval augmented generation", "vector database",
    "embedding model", "foundation model", "generative ai", "genai", "deep learning",
    "neural network", "machine learning model", "ai agent", "agentic", "tool calling",
    "text generation", "image generation", "diffusion model", "transformer model",
    "inference engine", "inference server", "gpu kernel", "tensor", "quantization",
    "fine-tuning", "lora", "model weights", "hugging face", "model hub",
)

# Words that are suggestive but appear in unrelated security contexts every day.
WEAK_TERMS: tuple[str, ...] = (
    "model", "ai", "ml", "gpu", "cuda", "neural", "inference", "training",
    "embedding", "vector", "agent", "prompt", "dataset", "pipeline", "chatbot",
    "copilot", "generative", "prediction", "classifier", "feature extraction",
)

_WORDY = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")


def _tokens(text: str) -> set[str]:
    return {t for t in _WORDY.findall(text.casefold()) if t}


def _has_term(text: str, term: str) -> bool:
    """Whole-word / whole-phrase match, so 'ray' does not match 'array'."""
    if " " in term:
        return term in text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


@dataclass(frozen=True)
class Relevance:
    included: bool
    confidence: str  # high | medium | none
    reason: str
    matched: tuple[str, ...]

    @property
    def needs_review(self) -> bool:
        return self.included and self.confidence != "high"


def classify(*headline: str | None, body: str | None = None, package: str | None = None) -> Relevance:
    """Decide whether a candidate belongs in an AI-security corpus.

    `headline` should carry the short, focused fields (title, component).  The
    long free-text `body` is searched for unambiguous terms only: generic words
    like "model" or "training" occur naturally in any lengthy vulnerability
    description, so counting them there would admit the whole CVE feed.
    """
    haystack = " ".join(t for t in (*headline, body) if t).casefold()
    head_text = " ".join(t for t in headline if t).casefold()

    if package:
        # A Go module path such as github.com/ollama/ollama must match on its
        # trailing segments, not the whole string.
        segments = [s for s in re.split(r"[/\\]", package.casefold()) if s]
        candidates = {re.sub(r"[\s_.-]+", "", package.casefold())}
        for segment in segments[-2:]:
            stripped = re.sub(r"[\s_.-]+", "", segment)
            candidates.add(stripped)
            candidates.add(stripped.removesuffix("cpp"))
        matched = candidates & AI_PACKAGES
        if matched:
            return Relevance(
                True, "high",
                f"受影响包名 '{package}' 属于已知 AI 基础设施组件",
                (package, *sorted(matched)),
            )

    strong = [t for t in STRONG_TERMS if _has_term(haystack, t)]
    if strong:
        sample = ", ".join(sorted(strong)[:3])
        return Relevance(True, "high", f"命中 AI 安全专有术语：{sample}", tuple(sorted(strong)))

    # Weak signals are judged on the headline only.  A substring test is also
    # ruled out here: "ai" would otherwise match "fail" or "domain".
    head_tokens = _tokens(head_text)
    weak = [t for t in WEAK_TERMS if t in head_tokens]
    # Two independent weak signals, or one weak signal alongside a security term.
    security = [t for t in ("vulnerability", "cve", "exploit", "advisory", "attack", "flaw")
                if t in head_tokens]
    if len(weak) >= 2 or (weak and security):
        sample = ", ".join(sorted(weak)[:3])
        return Relevance(
            True,
            "medium",
            f"仅命中通用术语（{sample}），证据不足以直接判定，已转人工复核",
            tuple(sorted(weak)),
        )

    return Relevance(False, "none", "未命中任何 AI 相关组件名或术语，不纳入 AI 安全情报库", ())
