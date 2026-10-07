"""统一配置加载、占位符识别与配置状态判断。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LLM_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DEFAULT_LLM_MODEL_NAME = "doubao-1-5-pro-32k-250115"
_ENV_LOADED = False

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def load_config() -> None:
    """加载项目根目录的 .env，系统环境变量优先。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
    _ENV_LOADED = True


def _get_env(name: str) -> str:
    load_config()
    value = os.getenv(name, "")
    return str(value).strip() if value is not None else ""


def is_placeholder(value) -> bool:
    """判断配置值是否为空或常见占位符。"""
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if "your_" in lowered or lowered.endswith("_here"):
        return True
    if "example.com" in lowered or "example.org" in lowered:
        return True
    if re.fullmatch(r"(your|replace|change|placeholder|todo|xxx)[-_].*", lowered):
        return True
    if lowered in {"your", "replace-me", "changeme", "placeholder", "todo", "xxx"}:
        return True
    return False


def _is_filled(value) -> bool:
    return not is_placeholder(value)


def _basic_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


def get_paypal_config() -> Dict[str, str]:
    return {
        "client_id": _get_env("PAYPAL_CLIENT_ID"),
        "client_secret": _get_env("PAYPAL_CLIENT_SECRET"),
        "merchant_email": _get_env("PAYPAL_MERCHANT_EMAIL"),
        "merchant_name": _get_env("PAYPAL_MERCHANT_NAME") or "TradePilot AI",
    }


def get_llm_config() -> Dict[str, str]:
    return {
        "api_key": _get_env("LLM_API_KEY"),
        "api_url": _get_env("LLM_API_URL") or DEFAULT_LLM_API_URL,
        "model_name": _get_env("LLM_MODEL_NAME") or DEFAULT_LLM_MODEL_NAME,
    }


def get_signal_config() -> Dict[str, str]:
    return {
        "api_url": _get_env("SIGNAL_API_URL"),
        "api_key": _get_env("SIGNAL_API_KEY"),
    }


def is_paypal_config_valid() -> bool:
    cfg = get_paypal_config()
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    merchant_email = cfg["merchant_email"]
    if not all(_is_filled(value) for value in (client_id, client_secret, merchant_email)):
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{20,}", client_id):
        return False
    if len(client_secret) <= 10:
        return False
    return _basic_email(merchant_email)


def get_paypal_config_status() -> Dict[str, object]:
    cfg = get_paypal_config()
    values = [cfg["client_id"], cfg["client_secret"], cfg["merchant_email"]]
    if not any(_is_filled(value) for value in values):
        return {
            "state": "not_configured",
            "label": "未配置（Demo模式）",
            "usable": False,
            "reason": "未填写 PayPal 配置，使用 Demo 模式。",
        }
    if is_paypal_config_valid():
        return {
            "state": "usable",
            "label": "配置可用",
            "usable": True,
            "reason": "本地格式校验通过，调用时仍需 PayPal 返回成功。",
        }
    return {
        "state": "unverified",
        "label": "已填写配置（未验证）",
        "usable": False,
        "reason": "配置已填写但格式未通过本地校验。",
    }


def is_llm_config_valid() -> bool:
    cfg = get_llm_config()
    key = cfg["api_key"]
    if not _is_filled(key) or len(key) < 16:
        return False
    if not cfg["api_url"].startswith(("http://", "https://")):
        return False
    return _is_filled(cfg["model_name"])


def get_llm_config_status() -> Dict[str, object]:
    cfg = get_llm_config()
    key = cfg["api_key"]
    if not key or is_placeholder(key):
        return {
            "state": "not_configured",
            "label": "未配置（Demo模式）",
            "usable": False,
            "reason": "未填写 LLM_API_KEY，合同审查使用基础规则检查。",
        }
    if is_llm_config_valid():
        return {
            "state": "usable",
            "label": "配置可用",
            "usable": True,
            "reason": "本地格式校验通过，调用时仍需 LLM 服务返回成功。",
        }
    return {
        "state": "unverified",
        "label": "已填写配置（未验证）",
        "usable": False,
        "reason": "配置已填写但本地格式校验未通过。",
    }


def get_signal_config_status() -> Dict[str, object]:
    cfg = get_signal_config()
    api_url = cfg["api_url"]
    if not api_url or is_placeholder(api_url):
        return {
            "state": "not_configured",
            "label": "未配置（Demo模式）",
            "usable": False,
            "reason": "未配置 SIGNAL_API_URL，使用 Demo Signal Provider。",
        }
    if not api_url.startswith(("http://", "https://")):
        return {
            "state": "unverified",
            "label": "已填写配置（未验证）",
            "usable": False,
            "reason": "SIGNAL_API_URL 格式无效。",
        }
    return {
        "state": "usable",
        "label": "配置可用",
        "usable": True,
        "reason": "本地格式校验通过。",
    }
