"""
运动（Exercise）子图状态定义模块。

入参：
无入参，仅用于集中描述与运动子图相关的状态字段。

返回值：
无返回值，提供 TypedDict 类型供运动子图节点使用。

关键逻辑：
在全局 GraphState 基础上，明确运动子图会读写的字段，便于 IDE 提示与静态类型检查。
"""

from typing import Any, Dict, TypedDict

from app.state import GraphState


class ExerciseState(GraphState, total=False):
    """
    运动子图在 GraphState 上关注和写入的字段定义。

    入参：
    无入参，本类型仅作为节点函数的类型提示使用。

    返回值：
    无返回值，通过字段说明当前子图会用到哪些状态。

    关键逻辑：
    - 继承全局 GraphState，使其兼容整张任务图的状态；
    - 明确运动子图会读取 / 写入的字段，便于团队协作与维护。
    """

    # 子图占位标记字段，标识运动子图已被执行
    exercise_placeholder: str

    # 运动建议内容（占位或真实训练方案文案）
    exercise_advice: str

    # 设备原始数据（当前为单日 JSON 解析后的字典）
    exercise_raw_device_data: Dict[str, Any]

    # 当日运动汇总信息，如总步数、运动时长、消耗能量等
    exercise_daily_summary: Dict[str, Any]

    # 心率统计信息，如静息心率、平均心率、最大/最小心率等
    exercise_heart_rate_stats: Dict[str, Any]

    # 分小时步数记录列表
    exercise_step_records: Any

    # 运动记录列表（如步行/慢跑/拉伸等）
    exercise_exercise_records: Any

    # 数据是否成功加载的标记，避免后续节点重复处理错误场景
    exercise_data_loaded: bool

    # 运动量水平标签（例如：偏低/适中/较高）
    exercise_activity_level: str

    # 步数目标是否达标
    exercise_step_goal_achieved: bool

    # 心率安全性等级（例如：安全/轻度偏高/需要关注）
    exercise_heart_safety_level: str

    # 是否存在久坐或活动不足的风险提示
    exercise_sedentary_warning: bool

    # 当日运动结构与节奏模式标签（例如：以中低强度有氧为主）
    exercise_pattern_type: str

    # 核心指标的简要文字概述，便于调试与后续子图使用
    exercise_metrics_summary: str

    # 用户画像占位字段，后续可由前端或上游节点写入个性化档案
    user_profile: Dict[str, Any]

