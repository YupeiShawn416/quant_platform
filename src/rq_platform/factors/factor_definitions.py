from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    name: str
    category: str
    description: str
    formula: str
    direction: str
    required_datasets: tuple[str, ...]
    default_universe: str = "all"
    default_rebalance_frequency: str = "daily"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_datasets"] = list(self.required_datasets)
        return data


BUILTIN_FACTORS: dict[str, FactorDefinition] = {
    "market_cap": FactorDefinition(
        factor_id="market_cap",
        name="Market Cap",
        category="valuation",
        description="市值因子，默认小市值为高分。",
        formula="-log(market_cap)",
        direction="lower_is_better",
        required_datasets=("valuation_1d",),
    ),
    "turnover_rate": FactorDefinition(
        factor_id="turnover_rate",
        name="Turnover Rate",
        category="liquidity",
        description="换手率因子，默认低换手为高分。",
        formula="-turnover_rate",
        direction="lower_is_better",
        required_datasets=("valuation_1d",),
    ),
    "momentum_20d": FactorDefinition(
        factor_id="momentum_20d",
        name="20D Momentum",
        category="price_volume",
        description="20 日动量，过去 20 日涨幅越高分数越高。",
        formula="close / close.shift(20) - 1",
        direction="higher_is_better",
        required_datasets=("prices_1d_pre",),
    ),
    "reversal_5d": FactorDefinition(
        factor_id="reversal_5d",
        name="5D Reversal",
        category="price_volume",
        description="5 日反转，过去 5 日跌幅越大分数越高。",
        formula="-(close / close.shift(5) - 1)",
        direction="lower_recent_return_is_better",
        required_datasets=("prices_1d_pre",),
    ),
    "volatility_20d": FactorDefinition(
        factor_id="volatility_20d",
        name="20D Volatility",
        category="risk",
        description="20 日日收益波动率，默认低波动为高分。",
        formula="-rolling_std(ret_1d, 20)",
        direction="lower_is_better",
        required_datasets=("prices_1d_pre",),
    ),
}

