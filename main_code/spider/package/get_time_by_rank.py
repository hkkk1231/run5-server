"""
根据排行榜数据计算配速评分的名次与时间分界线。

评分规则（按全程平均配速由高到低排名）：
- 前 20%：100 分
- 20% - 40%：90 分
- 40% - 60%：80 分
- 60% - 80%：70 分
- 最后 20%：60 分

本模块会从排行榜接口获取数据，按完成时间（毫秒）排序，
计算每个分数档位的名次范围和对应的时间阈值，并将时间换算成分钟展示。
"""

import json
import math
import sys
from dataclasses import dataclass
from typing import Any, Dict, List

from spider.package.core.logger_manager import setup_logger
from spider.package.data.get_rank import fetch_rank_data

logger = setup_logger("get_time_by_rank")

# 各分数档位对应的累计比例（按名次从 1 开始）
SCORE_PERCENT_MAPPING: Dict[int, float] = {
    100: 0.20,  # 前 20%
    90: 0.40,   # 前 40%（含 20% - 40%）
    80: 0.60,   # 前 60%
    70: 0.80,   # 前 80%
    60: 1.00,   # 全部（最后 20%）
}


@dataclass
class ScoreSegment:
    """单个分数档位的名次和时间信息。"""

    score: int
    start_rank: int
    end_rank: int
    threshold_ms: int

    @property
    def threshold_minutes(self) -> float:
        """将毫秒换算为分钟（浮点数）。"""
        return self.threshold_ms / 1000.0 / 60.0 if self.threshold_ms > 0 else 0.0


def calculate_score_rank_boundaries(total: int) -> Dict[int, int]:
    """
    根据总人数计算不同分数档位的名次分界线（截止名次，含）。

    Args:
        total: 排行榜总人数（如返回数据中的 `total` 字段）

    Returns:
        一个字典，key 为分数（100/90/80/70/60），value 为对应档位的截止名次（从 1 开始）。
        例如：
            {100: 1059, 90: 2118, 80: 3176, 70: 4235, 60: 5293}
    """
    total_int = int(total)
    if total_int <= 0:
        raise ValueError("总人数必须大于 0")

    boundaries: Dict[int, int] = {}

    for score, percent in SCORE_PERCENT_MAPPING.items():
        # 使用向上取整，确保至少有对应比例的人数进入该档位
        rank = max(1, min(total_int, math.ceil(total_int * percent)))
        boundaries[score] = rank

    logger.info("根据总人数 %s 计算分数分界线: %s", total_int, boundaries)
    return boundaries


def _parse_rank_data(raw_text: str) -> Dict[str, Any]:
    """解析排行榜 JSON 文本。"""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("解析排行榜 JSON 失败: %s", exc)
        raise
    return data


def _build_score_segments(rank_data: Dict[str, Any]) -> List[ScoreSegment]:
    """
    从排行榜数据构建每个分数档位的名次范围和时间阈值。

    排行榜数据结构示例：
        {"total": 5293, "rows": [{"completionTime": "369000", ...}, ...]}
    """
    rows = rank_data.get("rows") or []
    if not rows:
        raise ValueError("排行榜数据为空，无法计算分数分界线")

    # 按完成时间（毫秒）升序排序：用时越短排名越靠前
    sorted_rows = sorted(
        rows,
        key=lambda r: int(str(r.get("completionTime", "0")) or "0"),
    )

    total = int(rank_data.get("total") or len(sorted_rows))
    boundaries = calculate_score_rank_boundaries(total)

    segments: List[ScoreSegment] = []
    prev_end = 0

    # 按分数从高到低生成区间，避免区间重叠
    for score in sorted(SCORE_PERCENT_MAPPING.keys(), reverse=True):
        end_rank = boundaries[score]
        start_rank = prev_end + 1
        if start_rank > end_rank:
            continue

        # 阈值用时取该档位的最后一名
        index = min(end_rank, len(sorted_rows)) - 1
        row = sorted_rows[index]

        ms_str = str(row.get("completionTime", "0") or "0")
        try:
            threshold_ms = int(ms_str)
        except ValueError:
            threshold_ms = 0

        segments.append(
            ScoreSegment(
                score=score,
                start_rank=start_rank,
                end_rank=end_rank,
                threshold_ms=threshold_ms,
            )
        )
        prev_end = end_rank

    logger.info("已根据排行榜数据计算分数分界线和时间阈值")
    return segments


def _format_segments(segments: List[ScoreSegment]) -> str:
    """
    将分数档位的名次和时间信息格式化为可读字符串。
    """
    lines: List[str] = ["分数档位名次与时间分界线："]
    # 按分数从高到低输出
    for seg in sorted(segments, key=lambda s: s.score, reverse=True):
        lines.append(
            (
                f"{seg.score} 分：第 {seg.start_rank} 名 - 第 {seg.end_rank} 名，"
                f"时间阈值约 {seg.threshold_minutes:.2f} 分钟（{seg.threshold_ms} ms）"
            )
        )
    return "\n".join(lines)


def main() -> None:
    """
    命令行入口：直接运行本模块即可看到结果。

    使用方式（在 main_code 目录下）：
        python3 -m spider.package.get_time_by_rank
    """
    # 从排行榜接口获取原始数据
    raw_text = fetch_rank_data()
    rank_data = _parse_rank_data(raw_text)

    segments = _build_score_segments(rank_data)

    total = int(rank_data.get("total", len(rank_data.get("rows", []))))
    print(f"总人数：{total}")
    print(_format_segments(segments))


__all__ = [
    "calculate_score_rank_boundaries",
    "SCORE_PERCENT_MAPPING",
    "ScoreSegment",
    "main",
]


if __name__ == "__main__":
    # 允许通过 python -m spider.package.get_time_by_rank 直接运行
    main()
