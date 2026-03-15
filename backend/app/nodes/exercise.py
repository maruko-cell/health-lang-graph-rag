"""
运动建议（Exercise）子图模块。

入参：
无入参，本模块提供子图构建函数 build_exercise_graph() 供总图调用。

返回值：
通过 build_exercise_graph() 返回编译后的子图（CompiledGraph）。

关键逻辑：
基于设备端每日运动与心率数据，分三步完成：
1）加载并解析当天设备数据；
2）计算运动量、心率安全性与久坐等核心指标；
3）调用大模型生成结构化的中文运动健康报告，写入 exercise_advice 供汇总子图使用。
"""

import json
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.common.Prompt import EXERCISE_SYSTEM
from app.common.prompt_utils import build_system_human_messages
from app.common.thinkings import EXERCISE_THINKING
from app.config import BACKEND_ROOT
from app.llm_agent.agent import create_llm_agent
from app.state import GraphState
from app.nodes.exercise_state import ExerciseState


def _get_default_user_profile(state: ExerciseState) -> Dict[str, Any]:
    """
    功能描述：
    生成当前会话可用的用户画像字典，若状态中尚未写入真实画像，则返回占位的通用成人画像。

    入参说明：
    - state：ExerciseState，当前图状态，可选包含 user_profile 字段。

    返回值说明：
    - Dict[str, Any]：用户画像字典，至少包含 age、gender 等基础键。

    关键逻辑备注：
    - 优先使用 state 中已有的 user_profile；
    - 若不存在，则返回一个缺省的通用健康成年人画像，方便后续逻辑平滑扩展。
    """
    profile = (state.get("user_profile") or {}) if isinstance(state.get("user_profile"), dict) else {}
    if profile:
        return profile
    return {
        "age": None,
        "gender": None,
        "height_cm": None,
        "weight_kg": None,
        "chronic_diseases": [],
    }


def _exercise_load_device_data_node(state: ExerciseState) -> ExerciseState:
    """
    功能描述：
    从本地设备数据文件加载当日运动与心率信息，并写入运动子图专用状态字段。

    入参说明：
    - state：ExerciseState，当前图状态，可读 query 等上游字段。

    返回值说明：
    - ExerciseState：更新后的状态，包含 exercise_raw_device_data 及若干拆分字段，
      同时写入 exercise_data_loaded 用于后续节点判断。

    关键逻辑备注：
    - 当前阶段直接从 backend/app/data/device_data.json 读取单日示例数据；
    - 解析成功时拆分 daily_summary / heart_rate / step_records / exercise_records 等字段；
    - 解析失败时仅写入兜底提示到 exercise_advice，并标记 exercise_data_loaded 为 False。
    """
    new_state: ExerciseState = dict(state)
    new_state["exercise_placeholder"] = "exercise"

    device_path = BACKEND_ROOT / "app" / "data" / "device_data.json"
    try:
        with device_path.open("r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
    except Exception as exc:
        new_state["exercise_data_loaded"] = False
        new_state["exercise_advice"] = f"当前暂时无法读取设备运动数据，请稍后重试。错误信息：{exc}"
        prev_thinking = (new_state.get("thinking") or "").strip()
        thinking = "【运动思考】尝试读取设备运动数据失败，已返回兜底提示。"
        parts = [p for p in [prev_thinking, thinking] if p]
        new_state["thinking"] = "\n\n".join(parts)
        return new_state

    new_state["exercise_raw_device_data"] = data
    new_state["exercise_daily_summary"] = data.get("daily_summary") or {}
    new_state["exercise_heart_rate_stats"] = data.get("heart_rate") or {}
    new_state["exercise_step_records"] = data.get("step_records") or []
    new_state["exercise_exercise_records"] = data.get("exercise_records") or []
    new_state["exercise_data_loaded"] = True

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking = (
        "【运动思考】已成功加载当日设备运动与心率数据，"
        "接下来会基于这些数据计算运动量、心率安全性和久坐情况。"
    )
    parts = [p for p in [prev_thinking, thinking] if p]
    new_state["thinking"] = "\n\n".join(parts)

    return new_state


def _exercise_compute_metrics_node(state: ExerciseState) -> ExerciseState:
    """
    功能描述：
    基于设备原始数据计算运动量、步数达标情况、心率安全性、久坐风险和运动模式等核心指标。

    入参说明：
    - state：ExerciseState，当前图状态，需已包含 exercise_* 相关字段。

    返回值说明：
    - ExerciseState：更新后的状态，写入若干指标字段与简要概述 exercise_metrics_summary。

    关键逻辑备注：
    - 若 exercise_data_loaded 为 False 或缺失，则直接透传状态，不重复计算；
    - 目前采用简单规则阈值判断，后续可结合真实用户画像 user_profile 做个性化调整。
    """
    new_state: ExerciseState = dict(state)
    if not new_state.get("exercise_data_loaded"):
        return new_state

    profile = _get_default_user_profile(new_state)
    age = profile.get("age")

    daily_summary: Dict[str, Any] = new_state.get("exercise_daily_summary") or {}
    heart_stats: Dict[str, Any] = new_state.get("exercise_heart_rate_stats") or {}
    step_records: List[Dict[str, Any]] = new_state.get("exercise_step_records") or []
    exercise_records: List[Dict[str, Any]] = new_state.get("exercise_exercise_records") or []

    total_steps = int(daily_summary.get("total_steps") or 0)
    total_minutes = int(daily_summary.get("total_exercise_minutes") or 0)

    # 步数目标：默认 8000 步；如年龄大于 60 岁则略微降低目标
    step_goal = 8000
    if isinstance(age, int) and age >= 60:
        step_goal = 6000
    step_goal_achieved = total_steps >= step_goal

    if total_steps < 5000:
        activity_level = "偏低"
    elif total_steps < 10000:
        activity_level = "适中"
    else:
        activity_level = "较高"

    max_hr = heart_stats.get("max_heart_rate")
    heart_safety_level = "未知"
    if isinstance(max_hr, (int, float)):
        if isinstance(age, int) and age > 0:
            safe_upper = int((220 - age) * 0.85)
        else:
            safe_upper = 150
        if max_hr <= safe_upper:
            heart_safety_level = "安全"
        elif max_hr <= safe_upper + 15:
            heart_safety_level = "轻度偏高"
        else:
            heart_safety_level = "需要重点关注"

    sedentary_warning = False
    low_activity_blocks = 0
    for record in step_records:
        steps = record.get("steps")
        if isinstance(steps, int) and steps < 200:
            low_activity_blocks += 1
    if low_activity_blocks >= 2:
        sedentary_warning = True

    exercise_types = {str(item.get("type") or "").strip() for item in exercise_records if item}
    if "慢跑" in exercise_types:
        pattern_type = "以中高强度有氧为主，包含慢跑训练"
    elif "步行" in exercise_types and "拉伸" in exercise_types:
        pattern_type = "以中低强度步行为主，并有配套拉伸运动"
    elif "步行" in exercise_types:
        pattern_type = "以中低强度步行为主，整体节奏平稳"
    else:
        pattern_type = "运动类型相对单一，可适当增加有氧与拉伸搭配"

    summary_parts: List[str] = []
    summary_parts.append(f"今日总步数约为 {total_steps} 步，总运动时长约 {total_minutes} 分钟。")
    summary_parts.append(f"整体运动量水平：{activity_level}；步数目标 {'已达成' if step_goal_achieved else '尚未达标'}（目标约 {step_goal} 步）。")
    summary_parts.append(f"心率安全性评估：{heart_safety_level}。")
    if sedentary_warning:
        summary_parts.append("存在多个时段活动量较低，建议减少久坐时长、增加起身走动。")
    else:
        summary_parts.append("未见明显久坐风险，日内活动相对分散。")
    summary_parts.append(f"当日运动结构与节奏：{pattern_type}。")

    new_state["exercise_activity_level"] = activity_level
    new_state["exercise_step_goal_achieved"] = step_goal_achieved
    new_state["exercise_heart_safety_level"] = heart_safety_level
    new_state["exercise_sedentary_warning"] = sedentary_warning
    new_state["exercise_pattern_type"] = pattern_type
    new_state["exercise_metrics_summary"] = " ".join(summary_parts)

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking = "【运动思考】已基于设备运动数据计算运动量水平、心率安全性与久坐风险等核心指标。"
    parts = [p for p in [prev_thinking, thinking] if p]
    new_state["thinking"] = "\n\n".join(parts)

    return new_state


def _build_exercise_report_prompt(state: ExerciseState) -> str:
    """
    功能描述：
    将设备数据与已计算的运动指标整理为自然语言提示词，用于请求大模型生成运动健康报告。

    入参说明：
    - state：ExerciseState，已包含 exercise_metrics_summary 以及部分原始数据字段。

    返回值说明：
    - str：拼装好的单轮对话提示词文本。

    关键逻辑备注：
    - 对用户画像做显式说明：若不存在真实画像，则在提示中强调“按一般健康成年人标准评估”；
    - 将关键数据与指标按条目形式嵌入，方便模型围绕这些要点给出具体建议。
    """
    profile = _get_default_user_profile(state)
    age = profile.get("age") or "未提供"
    gender = profile.get("gender") or "未提供"
    height = profile.get("height_cm") or "未提供"
    weight = profile.get("weight_kg") or "未提供"
    chronic = profile.get("chronic_diseases") or []
    chronic_str = "、".join(chronic) if chronic else "未提供"

    daily_summary: Dict[str, Any] = state.get("exercise_daily_summary") or {}
    heart_stats: Dict[str, Any] = state.get("exercise_heart_rate_stats") or {}

    metrics_summary = (state.get("exercise_metrics_summary") or "").strip()

    return (
        "你是一名专业、温和且务实的运动健康管理教练，需要根据用户可穿戴设备采集的单日运动与心率数据，"
        "给出当天的运动表现评估以及第二天可执行的改进建议。\n\n"
        "【用户基础信息（可能不完整，仅供参考）】\n"
        f"- 年龄：{age}\n"
        f"- 性别：{gender}\n"
        f"- 身高（cm）：{height}\n"
        f"- 体重（kg）：{weight}\n"
        f"- 慢性疾病史：{chronic_str}\n"
        "若以上信息缺失或“未提供”，请按一般健康成年人标准做相对保守的建议，避免医学诊断与用药指导。\n\n"
        "【当日设备关键数据】\n"
        f"- 总步数：{daily_summary.get('total_steps', '未知')} 步\n"
        f"- 总运动时长：{daily_summary.get('total_exercise_minutes', '未知')} 分钟\n"
        f"- 估算能量消耗：{daily_summary.get('total_calories', '未知')} kcal\n"
        f"- 静息心率：{heart_stats.get('resting_heart_rate', '未知')} 次/分\n"
        f"- 平均心率：{heart_stats.get('average_heart_rate', '未知')} 次/分\n"
        f"- 最高心率：{heart_stats.get('max_heart_rate', '未知')} 次/分\n"
        f"- 最低心率：{heart_stats.get('min_heart_rate', '未知')} 次/分\n\n"
        "【系统预先计算的整体分析摘要】\n"
        f"{metrics_summary or '暂无摘要'}\n\n"
        "【请你输出】请使用中文，生成一份结构化、友好且可执行的当日运动健康报告，格式建议如下：\n"
        "1. 今日整体评价：用 2-3 句话概括今天运动表现的亮点与不足。\n"
        "2. 运动量与达标情况：结合步数、运动时长说明是否接近或达到推荐水平，并给出简单解释。\n"
        "3. 心率与安全性：用通俗语言说明心率是否在相对安全范围内，如有偏高/需关注请说明原因与建议（不要给药物和诊断）。\n"
        "4. 运动结构与生活节奏：根据全天活动分布，评价是否存在久坐、运动时间过于集中等问题，并给出改进方向。\n"
        "5. 明日可执行建议：给出 3-5 条具体可执行的小建议，例如“晚饭后增加 15 分钟快走”、“每工作 1 小时起身活动 3-5 分钟”等。\n"
        "请避免医学诊断与用药建议，重点放在生活方式与运动习惯的优化上。"
    )


def _exercise_generate_report_node(state: ExerciseState) -> ExerciseState:
    """
    功能描述：
    调用大模型，将设备数据与系统预计算指标整理为用户可读的当日运动健康报告，并写入 exercise_advice。

    入参说明：
    - state：ExerciseState，当前图状态，需要已包含 exercise_metrics_summary 等字段。

    返回值说明：
    - ExerciseState：更新后的状态，写入 exercise_advice，并在 thinking 中追加本节点的思考说明。

    关键逻辑备注：
    - 若前置节点未成功加载数据，则不再调用大模型，直接复用已有的兜底提示；
    - 调用失败时返回一段基于规则的简单运动建议，避免整体对话完全失败。
    """
    new_state: ExerciseState = dict(state)
    if not new_state.get("exercise_data_loaded"):
        return new_state

    human_content = _build_exercise_report_prompt(new_state)
    advice_text = ""
    try:
        cfg = create_llm_agent()
        messages = build_system_human_messages(EXERCISE_SYSTEM, human_content)
        advice_text = cfg.invoke_and_get_content(messages)
    except Exception as exc:
        advice_text = (
            "【简要运动建议】当前智能分析服务暂时不可用，先给出一些通用建议："
            "保持每日 6000-8000 步左右的中等强度活动，避免长时间久坐；"
            "根据自身情况安排每周 3-5 次有氧运动和 2-3 次抗阻训练；"
            "如有心血管基础疾病，请在医生指导下制定运动计划。"
            f"（错误信息：{exc}）"
        )

    if not advice_text:
        advice_text = (
            "今天的运动数据已分析完毕，总体建议是：保持适度活动、避免久坐，"
            "并根据自身体力逐步增加有氧与力量训练的频率和时长。"
        )

    new_state["exercise_advice"] = advice_text

    prev_thinking = (new_state.get("thinking") or "").strip()
    thinking = (
        EXERCISE_THINKING
        + " 已基于当日设备数据和预计算指标，为你生成一份更具体的运动健康报告和建议。"
    )
    parts = [p for p in [prev_thinking, thinking] if p]
    new_state["thinking"] = "\n\n".join(parts)

    return new_state


def build_exercise_graph() -> CompiledStateGraph:
    """
    功能描述：
    构建运动子图 StateGraph，将设备数据加载、指标计算与报告生成三个节点串联起来。

    入参说明：
    - 无入参，本函数仅负责组装并编译子图。

    返回值说明：
    - CompiledStateGraph：编译后的运动子图，可供总图作为节点调用。

    关键逻辑备注：
    - 子图节点顺序：entry -> exercise_load_device_data -> exercise_compute_metrics -> exercise_generate_report -> END；
    - 对外仍通过 exercise_advice 暴露最终的运动健康报告，兼容现有 summary 子图的汇总逻辑。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("exercise_load_device_data", _exercise_load_device_data_node)
    builder.add_node("exercise_compute_metrics", _exercise_compute_metrics_node)
    builder.add_node("exercise_generate_report", _exercise_generate_report_node)
    builder.set_entry_point("exercise_load_device_data")
    builder.add_edge("exercise_load_device_data", "exercise_compute_metrics")
    builder.add_edge("exercise_compute_metrics", "exercise_generate_report")
    builder.add_edge("exercise_generate_report", END)
    return builder.compile()
