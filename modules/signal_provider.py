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
from typing import Dict, List, Optional
import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class SignalProvider(ABC):
    """行情信号提供者抽象接口"""

    @abstractmethod
    def get_all_signals(self) -> Dict[str, dict]:
        """返回所有信号的当前状态"""
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
        self._df = self._load_data()

    def _load_data(self) -> pd.DataFrame:
        """加载合成演示数据"""
        if os.path.exists(self._data_path):
            df = pd.read_csv(self._data_path)
            df["date"] = pd.to_datetime(df["date"])
            return df
        # 如果数据文件不存在，生成临时合成数据
        return self._generate_synthetic_data()

    def _generate_synthetic_data(self) -> pd.DataFrame:
        """生成合成演示数据（仅在数据文件缺失时使用）"""
        np.random.seed(42)
        n_days = 500
        start_date = datetime(2024, 1, 2)
        dates = [start_date + timedelta(days=i) for i in range(n_days)]
        # 过滤周末
        dates = [d for d in dates if d.weekday() < 5][:400]

        base_rb = 3500
        base_hc = 3700
        base_cold = 4500
        base_spot = 3600

        data = []
        for i, d in enumerate(dates):
            trend = i * 0.3
            noise_rb = np.random.normal(0, 30)
            noise_hc = np.random.normal(0, 35)
            noise_cold = np.random.normal(0, 40)
            noise_spot = np.random.normal(0, 25)
            data.append({
                "date": d.strftime("%Y-%m-%d"),
                "rb_close": round(base_rb + trend + noise_rb, 0),
                "hc_close": round(base_hc + trend + noise_hc, 0),
                "cold_roll_close": round(base_cold + trend * 1.2 + noise_cold, 0),
                "rb_spot": round(base_spot + trend + noise_spot, 0),
            })
        return pd.DataFrame(data)

    @property
    def provider_name(self) -> str:
        return "Demo Signal Provider (Synthetic Data)"

    @property
    def is_demo(self) -> bool:
        return True

    def get_all_signals(self) -> Dict[str, dict]:
        """
        返回演示信号

        注意：这些信号基于合成数据和简化逻辑生成，仅用于演示目的。
        不代表任何真实市场观点或交易建议。
        """
        if len(self._df) < 50:
            return self._empty_signals()

        latest = self._df.iloc[-1]
        latest_date = latest["date"].strftime("%Y-%m-%d") if hasattr(latest["date"], "strftime") else str(latest["date"])

        # 简化的演示逻辑：基于近期价格波动率生成信号状态
        # 这不是生产策略，仅用于展示UI和流程
        recent = self._df.tail(60)
        rb_vol = recent["rb_close"].pct_change().std()
        hc_vol = recent["hc_close"].pct_change().std()

        # 演示信号：根据波动率水平设置不同的状态
        signals = {}

        # 信号1：冷轧-螺纹价差观察
        cold_rb_spread = latest["cold_roll_close"] - latest["rb_close"]
        cold_rb_z = self._demo_zscore(self._df["cold_roll_close"] - self._df["rb_close"])
        signals["cold_fut_rb"] = {
            "zh": "冷轧-螺纹价差观察",
            "direction": "观望" if abs(cold_rb_z) < 1.2 else ("价差偏高，关注收敛" if cold_rb_z > 0 else "价差偏低，关注修复"),
            "triggered": abs(cold_rb_z) >= 1.2,
            "confidence": "中" if abs(cold_rb_z) >= 1.5 else "低",
            "probability": 0.55 + min(abs(cold_rb_z) * 0.05, 0.15),  # 演示值，非真实回测
            "z": round(float(cold_rb_z), 2),
            "date": latest_date,
            "current_spread": round(float(cold_rb_spread), 0),
            "roll_mean": round(float((self._df["cold_roll_close"] - self._df["rb_close"]).tail(120).mean()), 0),
            "reasons": [
                "基于合成演示数据的简化价差分析",
                f"当前价差 {cold_rb_spread:.0f}，偏离120日均值 {abs(cold_rb_z):.1f} 个标准差",
                "本信号为演示模式，不构成投资建议",
            ],
        }

        # 信号2：冷轧-热卷价差观察
        cold_hc_spread = latest["cold_roll_close"] - latest["hc_close"]
        cold_hc_z = self._demo_zscore(self._df["cold_roll_close"] - self._df["hc_close"])
        signals["cold_fut_hc"] = {
            "zh": "冷轧-热卷价差观察",
            "direction": "观望" if abs(cold_hc_z) < 1.2 else ("价差偏高，关注收敛" if cold_hc_z > 0 else "价差偏低，关注修复"),
            "triggered": abs(cold_hc_z) >= 1.2,
            "confidence": "中" if abs(cold_hc_z) >= 1.5 else "低",
            "probability": 0.55 + min(abs(cold_hc_z) * 0.05, 0.15),
            "z": round(float(cold_hc_z), 2),
            "date": latest_date,
            "current_spread": round(float(cold_hc_spread), 0),
            "roll_mean": round(float((self._df["cold_roll_close"] - self._df["hc_close"]).tail(120).mean()), 0),
            "reasons": [
                "基于合成演示数据的简化价差分析",
                f"当前价差 {cold_hc_spread:.0f}，偏离120日均值 {abs(cold_hc_z):.1f} 个标准差",
                "本信号为演示模式，不构成投资建议",
            ],
        }

        # 信号3：螺纹基差观察
        rb_basis = latest["rb_spot"] - latest["rb_close"]
        rb_basis_z = self._demo_zscore(self._df["rb_spot"] - self._df["rb_close"])
        signals["rb_basis"] = {
            "zh": "螺纹基差观察",
            "direction": "观望" if abs(rb_basis_z) < 1.2 else ("现货升水偏高" if rb_basis_z > 0 else "期货升水偏高"),
            "triggered": abs(rb_basis_z) >= 1.2,
            "confidence": "中" if abs(rb_basis_z) >= 1.5 else "低",
            "probability": 0.55 + min(abs(rb_basis_z) * 0.05, 0.15),
            "z": round(float(rb_basis_z), 2),
            "date": latest_date,
            "current_spread": round(float(rb_basis), 0),
            "roll_mean": round(float((self._df["rb_spot"] - self._df["rb_close"]).tail(120).mean()), 0),
            "reasons": [
                "基于合成演示数据的简化基差分析",
                f"当前基差 {rb_basis:.0f}，偏离120日均值 {abs(rb_basis_z):.1f} 个标准差",
                "本信号为演示模式，不构成投资建议",
            ],
        }

        return signals

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

    def _empty_signals(self) -> Dict[str, dict]:
        """数据不足时返回空信号"""
        return {
            "cold_fut_rb": {"zh": "冷轧-螺纹价差观察", "direction": "数据不足", "triggered": False,
                             "confidence": "低", "probability": 0.0, "z": 0.0, "date": "N/A",
                             "reasons": ["演示数据不足"]},
            "cold_fut_hc": {"zh": "冷轧-热卷价差观察", "direction": "数据不足", "triggered": False,
                             "confidence": "低", "probability": 0.0, "z": 0.0, "date": "N/A",
                             "reasons": ["演示数据不足"]},
            "rb_basis": {"zh": "螺纹基差观察", "direction": "数据不足", "triggered": False,
                         "confidence": "低", "probability": 0.0, "z": 0.0, "date": "N/A",
                         "reasons": ["演示数据不足"]},
        }

    def get_price_chart_data(self) -> Dict[str, list]:
        """返回价格走势图表数据（最近180个交易日）"""
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
        self._api_url = api_url or os.environ.get("SIGNAL_API_URL", "")
        self._api_key = api_key or os.environ.get("SIGNAL_API_KEY", "")
        self._fallback = DemoSignalProvider()

    @property
    def provider_name(self) -> str:
        return "Remote Signal Provider (Production)"

    @property
    def is_demo(self) -> bool:
        return False

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def get_all_signals(self) -> Dict[str, dict]:
        """从远程API获取信号，失败时回退到Demo"""
        if not self._api_url:
            return self._fallback.get_all_signals()
        try:
            resp = requests.get(
                f"{self._api_url.rstrip('/')}/signals",
                headers=self._get_headers(),
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                # 远程API只返回信号状态，不返回策略参数
                return self._normalize_remote_signals(data)
        except Exception:
            pass
        # 失败时回退到Demo，并标注
        signals = self._fallback.get_all_signals()
        for sig in signals.values():
            sig["reasons"].insert(0, "⚠️ 远程信号服务不可用，当前显示演示数据")
        return signals

    def _normalize_remote_signals(self, data: dict) -> Dict[str, dict]:
        """将远程API返回的信号标准化为前端期望的格式"""
        normalized = {}
        signal_map = {
            "cold_fut_rb": "冷轧-螺纹价差观察",
            "cold_fut_hc": "冷轧-热卷价差观察",
            "rb_basis": "螺纹基差观察",
        }
        for key, zh in signal_map.items():
            sig_data = data.get(key, {})
            normalized[key] = {
                "zh": zh,
                "direction": sig_data.get("direction", "观望"),
                "triggered": sig_data.get("triggered", False),
                "confidence": sig_data.get("confidence", "低"),
                "probability": sig_data.get("probability", 0.0),
                "z": sig_data.get("z", 0.0),  # 远程API不应返回精确z值，这里仅作兼容
                "date": sig_data.get("date", "N/A"),
                "current_spread": sig_data.get("current_spread"),
                "roll_mean": sig_data.get("roll_mean"),
                "reasons": sig_data.get("reasons", ["由生产信号服务提供"]),
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
    api_url = os.environ.get("SIGNAL_API_URL", "")
    if api_url:
        return RemoteSignalProvider(api_url=api_url)
    return DemoSignalProvider()
