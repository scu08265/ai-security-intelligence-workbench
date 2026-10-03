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
        "litellm", "langfuse", "ragflow", "llama-box", "gpustack", "one-api", "new-api",
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
    # 中文术语：中文社区源（FreeBuf / 安全客 / 奇安信等）的标题与正文以中文为主，
    # 若只保留英文术语，中文文章会全部被过滤成 0 条。与上方英文术语一一对应。
    "人工智能", "生成式人工智能", "生成式ai", "aigc", "大语言模型", "大模型",
    "多模态大模型", "ai安全", "人工智能安全", "大模型安全", "提示词注入", "提示注入",
    "越狱攻击", "数据投毒", "模型投毒", "对抗样本", "对抗攻击", "模型窃取",
    "成员推理", "智能体", "智能体安全", "深度学习", "神经网络", "机器学习",
    "推理框架", "模型权重", "开源模型", "红队评估",
    # 2024 年之后常见但此前缺失的 AI 安全主题词
    "model context protocol", "deepfake", "深度伪造", "ai助手", "智能助手",
    "编程助手", "提示词", "大模型应用", "ai应用", "自动化攻击",
)

# Words that are suggestive but appear in unrelated security contexts every day.
WEAK_TERMS: tuple[str, ...] = (
    "model", "ai", "ml", "gpu", "cuda", "neural", "inference", "training",
    "embedding", "vector", "agent", "prompt", "dataset", "pipeline", "chatbot",
    "copilot", "generative", "prediction", "classifier", "feature extraction",
    "agentic", "assistant", "llmops", "多模态", "智能体", "大模型",
)

# A headline alone is ambiguous, so a weak AI signal has to be corroborated by
# an explicit security-intent word.  `security` is included because vendor and
# community feeds routinely write "AI security" rather than naming a CVE.
SECURITY_TERMS: tuple[str, ...] = (
    "vulnerability", "vulnerabilities", "cve", "exploit", "advisory", "attack",
    "flaw", "security", "malware", "ransomware", "phishing", "threat", "breach",
    # 中文安全意图词：中文标题不分词，按子串匹配
    "安全", "漏洞", "攻击", "利用", "木马", "勒索", "注入", "越权", "提权",
    "后门", "渗透", "威胁", "免杀", "bypass",
)

# Unicode punctuation that silently breaks ASCII tokenisation.  Feeds emit
# "AI-powered" with U+2011 (non-breaking hyphen) as often as a plain hyphen,
# and the CJK range is never captured by an ASCII word regex at all.
_PUNCT_FIXES = {
    "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "−": "-", " ": " ", "　": " ",
}

# Shortest component name that may be matched inside a free-text headline.
AI_PACKAGE_HEADLINE_MIN_LEN = 4

_CJK = re.compile(r"[㐀-鿿]")


def _normalise(text: str) -> str:
    for bad, good in _PUNCT_FIXES.items():
        if bad in text:
            text = text.replace(bad, good)
    return text


def _has_term(text: str, term: str) -> bool:
    """Whole-word / whole-phrase match, so 'ray' does not match 'array'.

    CJK terms have no word boundaries and are not produced by `_tokens`, so
    they are matched as substrings instead.
    """
    if _CJK.search(term):
        return term in text
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
    haystack = _normalise(" ".join(t for t in (*headline, body) if t)).casefold()
    head_text = _normalise(" ".join(t for t in headline if t)).casefold()

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

    # Blog and community feeds name the component in the headline ("LiteLLM
    # 密钥泄露漏洞分析") but never pass a `package` argument, so the package
    # table above would never fire for them.  Names shorter than four
    # characters are excluded: "ray", "jax" and "jan" match ordinary prose.
    named = sorted(
        p for p in AI_PACKAGES if len(p) >= AI_PACKAGE_HEADLINE_MIN_LEN
        and _has_term(head_text, p)
    )
    if named:
        return Relevance(
            True, "high",
            f"标题命中已知 AI 基础设施组件名：{', '.join(named[:3])}",
            tuple(named),
        )

    strong = [t for t in STRONG_TERMS if _has_term(haystack, t)]
    if strong:
        sample = ", ".join(sorted(strong)[:3])
        return Relevance(True, "high", f"命中 AI 安全专有术语：{sample}", tuple(sorted(strong)))

    # Weak signals are judged on the headline only.  A substring test is also
    # ruled out here: "ai" would otherwise match "fail" or "domain".
    # Match on word boundaries rather than on the token set: `_WORDY` keeps
    # hyphenated words whole, so "AI-powered" would tokenise as one item and
    # never match the weak term "ai".  A boundary test still refuses "array"
    # for "ray" and "domain" for "ai".
    weak = [t for t in WEAK_TERMS if _has_term(head_text, t)]
    # Two independent weak signals, or one weak signal alongside a security
    # term.  CJK terms are matched as substrings: a Chinese headline is not
    # split into ASCII tokens, so a token test would never fire.
    security = [t for t in SECURITY_TERMS if _has_term(head_text, t)]
    if len(weak) >= 2 or (weak and security):
        sample = ", ".join(sorted(weak)[:3])
        evidence = ", ".join(sorted(security)[:2])
        detail = f"通用术语 [{sample}]"
        if evidence:
            detail += f" + 安全意图词 [{evidence}]"
        return Relevance(
            True,
            "medium",
            f"{detail}：证据不足以直接判定，已转人工复核",
            tuple(sorted(weak)) + tuple(sorted(security)),
        )

    return Relevance(False, "none", "未命中任何 AI 相关组件名或术语，不纳入 AI 安全情报库", ())
