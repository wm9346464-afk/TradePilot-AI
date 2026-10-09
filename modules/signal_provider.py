"""
Signal Provider 抽象接口与实现

本模块定义行情信号的统一接口，并提供两种实现：
- DemoSignalProvider: 默认实现，使用合成演示数据，公开可独立运行
- RemoteSignalProvider: 可选实现，调用私有生产服务获取信号（需要配置API端点）

重要说明：
本公开仓库中的 DemoSignalProvider 使用合成数据，仅用于演示系统架构和用户流程。
它不包含任何生产级策略参数、真实回测结果或交易建议。
生产级信号系统不在本仓库范围内，如需接入请通过 RemoteSignalProvider 配置私有端点。
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import os
import sys
from pathlib import Path
import requests
import pandas as pd
import numpy as np
import logging


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.generate_demo_data import generate_demo_data
except ImportError:  # pragma: no cover - only used when the script is missing
    generate_demo_data = None


logger = logging.getLogger(__name__)

from modules.config import get_signal_config, is_placeholder, load_config

load_config()

# Bilingual signal metadata (module-level constants)
SIGNAL_META = {
    "cold_fut_rb": {
        "zh": {"name": "冷轧-螺纹价差观察", "wait": "观望", "high": "价差偏高，关注收敛", "low": "价差偏低，关注修复"},
        "en": {"name": "Cold-rolled vs Rebar Spread", "wait": "Neutral", "high": "Spread elevated, watch convergence", "low": "Spread depressed, watch recovery"},
    },
    "cold_fut_hc": {
        "zh": {"name": "冷轧-热卷价差观察", "wait": "观望", "high": "价差偏高，关注收敛", "low": "价差偏低，关注修复"},
        "en": {"name": "Cold-rolled vs Hot-rolled Spread", "wait": "Neutral", "high": "Spread elevated, watch convergence", "low": "Spread depressed, watch recovery"},
    },
    "rb_basis": {
        "zh": {"name": "螺纹基差观察", "wait": "观望", "high": "现货升水偏高", "low": "期货升水偏高"},
        "en": {"name": "Rebar Basis Observation", "wait": "Neutral", "high": "Spot premium elevated", "low": "Futures premium elevated"},
    },
}
CONF_MAP = {"zh": {"高": "高", "中": "中", "低": "低"}, "en": {"高": "High", "中": "Medium", "低": "Low"}}
REASON_TEMPLATES = {
    "zh": {
        "spread": "基于合成演示数据的简化价差分析",
        "basis": "基于合成演示数据的简化基差分析",
        "spread_detail": "当前价差 {val:.0f}，偏离120日均值 {z:.1f} 个标准差",
        "basis_detail": "当前基差 {val:.0f}，偏离120日均值 {z:.1f} 个标准差",
        "disclaimer": "本信号为演示模式，不构成投资建议",
    },
    "en": {
        "spread": "Simplified spread analysis based on synthetic demo data",
        "basis": "Simplified basis analysis based on synthetic demo data",
        "spread_detail": "Current spread {val:.0f}, deviates from 120-day mean by {z:.1f} standard deviations",
        "basis_detail": "Current basis {val:.0f}, deviates from 120-day mean by {z:.1f} standard deviations",
        "disclaimer": "This signal is in demo mode, does not constitute investment advice",
    },
}


class SignalProvider(ABC):
    """行情信号提供者抽象接口"""

    @abstractmethod
    def get_all_signals(self, lang: str = "zh") -> Dict[str, object]:
        """返回 source/degraded/error_code/signals/as_of 结构化结果
        lang: "zh" or "en", controls signal names/directions/reasons language
        """
        pass

    @abstractmethod
    def get_price_chart_data(self) -> Dict[str, list]:
        """返回价格走势图表数据"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名称"""
        pass

    @property
    @abstractmethod
    def is_demo(self) -> bool:
        """是否为演示模式"""
        pass


class DemoSignalProvider(SignalProvider):
    """
    演示信号提供者

    使用合成数据生成演示信号，用于展示系统架构和用户流程。
    不包含任何真实生产策略参数或回测结果。
    """

    def __init__(self, data_path: Optional[str] = None):
        self._data_path = data_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "demo_market_data.csv"
        )
        self._data_warning = ""
        self._df = self._load_data()

    def _load_data(self) -> pd.DataFrame:
        """加载合成演示数据"""
        required_columns = {
            "date",
            "rb_close",
            "hc_close",
            "cold_roll_close",
            "rb_spot",
        }
        if os.path.exists(self._data_path):
            try:
                df = pd.read_csv(self._data_path)
                missing = required_columns.difference(df.columns)
                if missing:
                    raise ValueError(f"演示数据缺少字段: {sorted(missing)}")
                df["date"] = pd.to_datetime(df["date"], errors="raise")
                return df
            except Exception as exc:
                self._data_warning = f"演示数据读取失败，已改用生成器: {exc}"
        # 如果数据文件不存在或损坏，直接从可复现生成器生成。
        return self._generate_synthetic_data()

    def _generate_synthetic_data(self) -> pd.DataFrame:
        """生成合成演示数据（仅在数据文件缺失时使用）"""
        if generate_demo_data is None:
            raise RuntimeError(
                "缺少 scripts/generate_demo_data.py，无法生成可复现演示数据"
            )
        df = generate_demo_data()
        df["date"] = pd.to_datetime(df["date"])
        return df

    @property
    def provider_name(self) -> str:
        return "Demo Signal Provider (Synthetic Data)"

    @property
    def is_demo(self) -> bool:
        return True

    @property
    def signals_source(self) -> str:
        return "Demo Signal Provider (Synthetic Data)"

    @property
    def chart_source(self) -> str:
        return self.signals_source

    @property
    def fallback_reason(self) -> str:
        return self._data_warning

    @property
    def as_of(self) -> str:
        if self._df.empty:
            return "N/A"
        latest = self._df["date"].iloc[-1]
        if hasattr(latest, "strftime"):
            return latest.strftime("%Y-%m-%d")
        return str(latest)

    def get_all_signals(self, lang: str = "zh") -> Dict[str, dict]:
        """
        返回演示信号

        注意：这些信号基于合成数据和简化逻辑生成，仅用于演示目的。
        不代表任何真实市场观点或交易建议。
        lang: "zh" or "en"
        """
        if len(self._df) < 50:
            return self._make_bundle(
                self._empty_signals(lang),
                degraded=bool(self._data_warning),
                error_code="DEMO_DATA_INSUFFICIENT",
                fallback_reason=self._data_warning,
            )

        latest = self._df.iloc[-1]
        latest_date = (
            latest["date"].strftime("%Y-%m-%d")
            if hasattr(latest["date"], "strftime")
            else str(latest["date"])
        )

        # 简化的演示逻辑：基于近期价格波动率生成信号状态
        # 这不是生产策略，仅用于展示UI和流程
        recent = self._df.tail(60)
        rb_vol = recent["rb_close"].pct_change().std()
        hc_vol = recent["hc_close"].pct_change().std()

        # 演示信号：根据波动率水平设置不同的状态
        if lang not in ("zh", "en"):
            lang = "zh"
        rt = REASON_TEMPLATES[lang]
        cm = CONF_MAP[lang]
        signals = {}

        # 信号1：冷轧-螺纹价差观察
        cold_rb_spread = latest["cold_roll_close"] - latest["rb_close"]
        cold_rb_z = self._demo_zscore(self._df["cold_roll_close"] - self._df["rb_close"])
        meta1 = SIGNAL_META["cold_fut_rb"][lang]
        signals["cold_fut_rb"] = {
            "zh": meta1["name"],
            "direction": meta1["wait"] if abs(cold_rb_z) < 1.2 else (meta1["high"] if cold_rb_z > 0 else meta1["low"]),
            "triggered": abs(cold_rb_z) >= 1.2,
            "confidence": cm["中"] if abs(cold_rb_z) >= 1.5 else cm["低"],
            "probability": 0.55 + min(abs(cold_rb_z) * 0.05, 0.15),  # 演示值，非真实回测
            "z": round(float(cold_rb_z), 2),
            "date": latest_date,
            "current_spread": round(float(cold_rb_spread), 0),
            "roll_mean": round(float((self._df["cold_roll_close"] - self._df["rb_close"]).tail(120).mean()), 0),
            "reasons": [
                rt["spread"],
                rt["spread_detail"].format(val=cold_rb_spread, z=abs(cold_rb_z)),
                rt["disclaimer"],
            ],
        }

        # 信号2：冷轧-热卷价差观察
        cold_hc_spread = latest["cold_roll_close"] - latest["hc_close"]
        cold_hc_z = self._demo_zscore(self._df["cold_roll_close"] - self._df["hc_close"])
        meta2 = SIGNAL_META["cold_fut_hc"][lang]
        signals["cold_fut_hc"] = {
            "zh": meta2["name"],
            "direction": meta2["wait"] if abs(cold_hc_z) < 1.2 else (meta2["high"] if cold_hc_z > 0 else meta2["low"]),
            "triggered": abs(cold_hc_z) >= 1.2,
            "confidence": cm["中"] if abs(cold_hc_z) >= 1.5 else cm["低"],
            "probability": 0.55 + min(abs(cold_hc_z) * 0.05, 0.15),
            "z": round(float(cold_hc_z), 2),
            "date": latest_date,
            "current_spread": round(float(cold_hc_spread), 0),
            "roll_mean": round(float((self._df["cold_roll_close"] - self._df["hc_close"]).tail(120).mean()), 0),
            "reasons": [
                rt["spread"],
                rt["spread_detail"].format(val=cold_hc_spread, z=abs(cold_hc_z)),
                rt["disclaimer"],
            ],
        }

        # 信号3：螺纹基差观察
        rb_basis = latest["rb_spot"] - latest["rb_close"]
        rb_basis_z = self._demo_zscore(self._df["rb_spot"] - self._df["rb_close"])
        meta3 = SIGNAL_META["rb_basis"][lang]
        signals["rb_basis"] = {
            "zh": meta3["name"],
            "direction": meta3["wait"] if abs(rb_basis_z) < 1.2 else (meta3["high"] if rb_basis_z > 0 else meta3["low"]),
            "triggered": abs(rb_basis_z) >= 1.2,
            "confidence": cm["中"] if abs(rb_basis_z) >= 1.5 else cm["低"],
            "probability": 0.55 + min(abs(rb_basis_z) * 0.05, 0.15),
            "z": round(float(rb_basis_z), 2),
            "date": latest_date,
            "current_spread": round(float(rb_basis), 0),
            "roll_mean": round(float((self._df["rb_spot"] - self._df["rb_close"]).tail(120).mean()), 0),
            "reasons": [
                rt["basis"],
                rt["basis_detail"].format(val=rb_basis, z=abs(rb_basis_z)),
                rt["disclaimer"],
            ],
        }

        return self._make_bundle(
            signals,
            degraded=bool(self._data_warning),
            error_code="DEMO_DATA_FALLBACK" if self._data_warning else "",
            fallback_reason=self._data_warning,
        )

    def _make_bundle(self, signals: Dict[str, dict], degraded: bool, error_code: str, fallback_reason: str) -> Dict:
        return {
            "source": self.signals_source,
            "degraded": degraded,
            "error_code": error_code,
            "fallback_reason": fallback_reason,
            "signals": signals,
            "as_of": self.as_of,
            "is_demo": True,
        }

    def _demo_zscore(self, series: pd.Series, window: int = 120) -> float:
        """演示用简化z-score计算（非生产策略参数）"""
        if len(series) < window:
            return 0.0
        recent = series.tail(window)
        mean = recent.mean()
        std = recent.std()
        if std == 0 or np.isnan(std):
            return 0.0
        return float((series.iloc[-1] - mean) / std)

    def _empty_signals(self, lang: str = "zh") -> Dict[str, dict]:
        """数据不足时返回空信号"""
        if lang not in ("zh", "en"):
            lang = "zh"
        names = {
            "zh": {"cold_fut_rb": "冷轧-螺纹价差观察", "cold_fut_hc": "冷轧-热卷价差观察", "rb_basis": "螺纹基差观察",
                   "direction": "数据不足", "reason": "演示数据不足", "conf": "低"},
            "en": {"cold_fut_rb": "Cold-rolled vs Rebar Spread", "cold_fut_hc": "Cold-rolled vs Hot-rolled Spread", "rb_basis": "Rebar Basis Observation",
                   "direction": "Insufficient Data", "reason": "Demo data insufficient", "conf": "Low"},
        }
        n = names[lang]
        return {
            "cold_fut_rb": {"zh": n["cold_fut_rb"], "direction": n["direction"], "triggered": False,
                             "confidence": n["conf"], "probability": 0.0, "z": 0.0, "date": "N/A",
                             "reasons": [n["reason"]]},
            "cold_fut_hc": {"zh": n["cold_fut_hc"], "direction": n["direction"], "triggered": False,
                             "confidence": n["conf"], "probability": 0.0, "z": 0.0, "date": "N/A",
                             "reasons": [n["reason"]]},
            "rb_basis": {"zh": n["rb_basis"], "direction": n["direction"], "triggered": False,
                         "confidence": n["conf"], "probability": 0.0, "z": 0.0, "date": "N/A",
                         "reasons": [n["reason"]]},
        }

    def get_price_chart_data(self) -> Dict[str, list]:
        """返回价格走势图表数据（最近180个数据点）"""
        recent = self._df.tail(180)
        return {
            "dates": [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in recent["date"]],
            "cold_roll": recent["cold_roll_close"].tolist(),
            "hc_futures": recent["hc_close"].tolist(),
            "rb_futures": recent["rb_close"].tolist(),
            "rb_spot": recent["rb_spot"].tolist(),
        }


class RemoteSignalProvider(SignalProvider):
    """
    远程信号提供者（可选）

    调用私有生产服务获取信号。私有API只返回信号状态，不返回策略参数。
    需要配置环境变量 SIGNAL_API_URL 和可选的 SIGNAL_API_KEY。

    注意：本公开仓库不包含生产服务的实现或部署代码。
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        cfg = get_signal_config()
        self._api_url = api_url if api_url is not None else cfg["api_url"]
        self._api_key = api_key if api_key is not None else cfg["api_key"]
        self._fallback = DemoSignalProvider()

    @property
    def provider_name(self) -> str:
        if self._api_url:
            return "Remote Signal Provider (Production)"
        return self._fallback.provider_name

    @property
    def is_demo(self) -> bool:
        return not bool(self._api_url)

    @property
    def signals_source(self) -> str:
        if not self._api_url:
            return self._fallback.signals_source
        return "Remote Signal Provider (Production)"

    @property
    def chart_source(self) -> str:
        return self._fallback.chart_source

    @property
    def fallback_reason(self) -> str:
        return ""

    @property
    def as_of(self) -> str:
        return self._fallback.as_of

    @staticmethod
    def _coerce_float(value, default=None):
        if value is None or isinstance(value, bool):
            return default
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if not np.isfinite(result):
            return default
        return result

    @staticmethod
    def _coerce_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in {0, 1}:
            return value == 1
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                return True
            if normalized in {"false", "0", "no", "n", "off"}:
                return False
        raise ValueError("INVALID_REMOTE_PAYLOAD")

    @staticmethod
    def _coerce_reasons(value) -> list:
        default = ["由生产信号服务提供"]
        if value is None:
            return default
        if isinstance(value, str):
            return [value] if value.strip() else default
        if isinstance(value, (list, tuple)):
            reasons = [str(item).strip() for item in value if str(item).strip()]
            return reasons or default
        return [str(value)]

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def get_all_signals(self, lang: str = "zh") -> Dict[str, dict]:
        """从远程API获取信号，返回结构化结果；失败时回退到Demo。"""
        if not self._api_url or is_placeholder(self._api_url):
            return self._fallback_signals("未配置 SIGNAL_API_URL" if lang == "zh" else "SIGNAL_API_URL not configured", "REMOTE_NOT_CONFIGURED", lang=lang)
        try:
            resp = requests.get(
                f"{self._api_url.rstrip('/')}/signals",
                headers=self._get_headers(),
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError("INVALID_REMOTE_PAYLOAD")
            normalized = self._normalize_remote_signals(data)
            dates = [
                item.get("date")
                for item in normalized.values()
                if item.get("date") and item.get("date") != "N/A"
            ]
            return {
                "source": "Remote Signal Provider (Production)",
                "degraded": False,
                "error_code": "",
                "fallback_reason": "",
                "signals": normalized,
                "as_of": max(dates) if dates else self._fallback.as_of,
                "is_demo": False,
            }
        except ValueError as exc:
            return self._fallback_signals("远程响应格式无效" if lang == "zh" else "Invalid remote response", "INVALID_REMOTE_PAYLOAD", lang=lang)
        except Exception as exc:
            return self._fallback_signals(
                f"远程信号服务不可用: {type(exc).__name__}: {exc}" if lang == "zh" else f"Remote signal service unavailable: {type(exc).__name__}: {exc}",
                "REMOTE_UNAVAILABLE",
                lang=lang,
            )

    def _fallback_signals(self, reason: str, error_code: str, lang: str = "zh") -> Dict[str, dict]:
        """回退到Demo并返回本次调用的结构化降级状态。"""
        logger.warning("远程信号降级为Demo: %s", reason)
        bundle = self._fallback.get_all_signals(lang=lang)
        signals = bundle["signals"]
        for sig in signals.values():
            reasons = sig.get("reasons")
            if not isinstance(reasons, list):
                reasons = [str(reasons)]
            sig["reasons"] = [reason] + reasons
        return {
            **bundle,
            "degraded": True,
            "error_code": error_code,
            "fallback_reason": reason,
            "is_demo": True,
        }

    def _normalize_remote_signals(self, data: dict) -> Dict[str, dict]:
        """将远程API返回的信号标准化为前端期望的格式"""
        if not isinstance(data, dict):
            raise ValueError("INVALID_REMOTE_PAYLOAD")

        normalized = {}
        signal_map = {
            "cold_fut_rb": "冷轧-螺纹价差观察",
            "cold_fut_hc": "冷轧-热卷价差观察",
            "rb_basis": "螺纹基差观察",
        }
        for key, zh in signal_map.items():
            raw_signal = data.get(key)
            if not isinstance(raw_signal, dict):
                raise ValueError("INVALID_REMOTE_PAYLOAD")
            for field in ("direction", "triggered", "probability"):
                if field not in raw_signal:
                    raise ValueError("INVALID_REMOTE_PAYLOAD")

            direction = raw_signal.get("direction")
            if not isinstance(direction, str) or not direction.strip():
                raise ValueError("INVALID_REMOTE_PAYLOAD")

            probability = self._coerce_float(raw_signal.get("probability"), default=None)
            if probability is None or probability < 0:
                raise ValueError("INVALID_REMOTE_PAYLOAD")
            if probability > 1.0 and probability <= 100.0:
                probability = probability / 100.0
            if probability > 1.0:
                raise ValueError("INVALID_REMOTE_PAYLOAD")

            confidence = str(raw_signal.get("confidence", "低"))
            if confidence not in {"高", "中", "低"}:
                confidence = "低"

            normalized[key] = {
                "zh": zh,
                "direction": direction.strip(),
                "triggered": self._coerce_bool(raw_signal.get("triggered")),
                "confidence": confidence,
                "probability": probability,
                "z": self._coerce_float(raw_signal.get("z"), default=None),
                "date": str(raw_signal.get("date", "N/A")),
                "current_spread": self._coerce_float(
                    raw_signal.get("current_spread"), default=None
                ),
                "roll_mean": self._coerce_float(
                    raw_signal.get("roll_mean"), default=None
                ),
                "reasons": self._coerce_reasons(raw_signal.get("reasons")),
            }
        return normalized

    def get_price_chart_data(self) -> Dict[str, list]:
        """价格图表数据使用Demo数据（远程API不提供历史价格）"""
        return self._fallback.get_price_chart_data()


def get_default_provider() -> SignalProvider:
    """
    获取默认信号提供者

    如果配置了 SIGNAL_API_URL 环境变量，则使用 RemoteSignalProvider；
    否则使用 DemoSignalProvider（默认，无需任何配置即可运行）。
    """
    cfg = get_signal_config()
    if cfg["api_url"] and not is_placeholder(cfg["api_url"]):
        return RemoteSignalProvider(api_url=cfg["api_url"], api_key=cfg["api_key"])
    return DemoSignalProvider()
