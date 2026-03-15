"""
自画像（Selfie）子图模块：根据用户画像与用户描述生成自画像图像。

入参：
无入参，本模块提供子图构建函数 build_selfie_graph() 供总图调用。

返回值：
通过 build_selfie_graph() 返回编译后的子图（CompiledStateGraph）。

关键逻辑：
从 state 读取 user_profile、query，拼成图像描述 prompt，调用智谱图像生成 API（glm-image），
将结果图片 URL 与说明写入 selfie_image_url、selfie_advice。
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.common.thinkings import (
    SELFIE_THINKING,
    SELFIE_THINKING_DONE,
    SELFIE_THINKING_ERROR,
)
from app.config import (
    USER_AGE,
    USER_BMI,
    USER_BMI_CATEGORY,
    USER_HEIGHT,
    USER_NAME,
    USER_SEX,
    USER_WEIGHT,
    ZHIPUAI_API_KEY,
    ZHIPUAI_SELF_MODEL,
    ZHIPUAI_URL,
)
from app.state import GraphState
from app.nodes.selfie_state import SelfieState


def _build_selfie_prompt(profile: Dict[str, Any], query: str) -> str:
    """
    根据用户画像与用户输入拼成自画像生成的文本描述（prompt），要求卡通风格、全身照，性别与身高体重 BMI 参考 profile/config。

    入参：
    - profile：dict，用户画像（age、gender、height_cm、weight_kg、bmi、bmi_category、name 等），可为空。
    - query：str，用户本轮输入，可含风格关键词。

    返回值：
    str：用于智谱图像生成 API 的 prompt，明确卡通、全身、性别与体型。

    关键逻辑：
    首句用中英关键词锁定「卡通女性全身」；再写年龄身高体重 BMI；结尾再次重复卡通全身与性别，提高模型遵循度。
    """
    age = profile.get("age")
    gender = profile.get("gender")
    height_cm = profile.get("height_cm")
    weight_kg = profile.get("weight_kg")
    bmi = profile.get("bmi")
    bmi_category = profile.get("bmi_category")

    gender_cn = "年轻人"
    if isinstance(gender, str) and gender.strip():
        g = gender.strip().lower()
        if g == "female" or g == "f" or "女" in gender.strip():
            gender_cn = "女性"
        elif g == "male" or g == "m" or ("男" in gender.strip() and "女" not in gender.strip()):
            gender_cn = "男性"

    age_cn = ""
    if isinstance(age, (int, float)) and age > 0:
        age_cn = f"{int(age)}岁"

    body_desc = []
    if isinstance(height_cm, (int, float)) and height_cm > 0:
        body_desc.append(f"身高{int(height_cm)}厘米")
    if isinstance(weight_kg, (int, float)) and weight_kg > 0:
        body_desc.append(f"体重{weight_kg}公斤")
    if bmi:
        body_desc.append(f"BMI{bmi}")
    if bmi_category:
        body_desc.append(bmi_category)

    # 首句强约束：卡通 + 全身 + 性别，便于模型优先满足
    first = f"卡通风格，动漫风格，非写实，可爱二次元。全身照，从头到脚完整人物，竖构图。{gender_cn}，"
    if age_cn:
        first += age_cn + "，"
    if body_desc:
        first += "，".join(body_desc) + "。"
    first += "卡通插画全身像，非写实，非照片，人物为" + gender_cn + "。"

    user_note = (query or "").strip()
    if user_note:
        first += " 用户补充：" + user_note[:150]
    return first


def _call_zhipu_image_api(prompt: str) -> tuple[str | None, str]:
    """
    调用智谱图像生成 API，返回图片 URL 或错误信息。

    入参：
    - prompt：str，图像描述文本。

    返回值：
    tuple[str | None, str]：(图片 URL 或 None，说明文案或错误信息)。

    关键逻辑：
    POST {ZHIPUAI_URL}images/generations，Bearer 鉴权，解析 data[0].url；失败时返回 (None, 错误说明)。
    """
    if not (ZHIPUAI_API_KEY or "").strip():
        return None, "【自画像】未配置智谱 API Key，无法生成图像。"
    base_url = (ZHIPUAI_URL or "").rstrip("/")
    url = f"{base_url}/images/generations"
    # 竖版尺寸利于全身构图（从头到脚）
    body = {
        "model": ZHIPUAI_SELF_MODEL or "glm-image",
        "prompt": prompt,
        "size": "960x1728",
        "quality": "hd",
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {ZHIPUAI_API_KEY.strip()}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
        out = json.loads(raw)
        items = out.get("data") if isinstance(out.get("data"), list) else []
        if items and isinstance(items[0], dict):
            link = items[0].get("url")
            if isinstance(link, str) and link.strip():
                return link.strip(), f"已为您的生成自画像，请查收：{link.strip()}"
        return None, "【自画像】接口返回格式异常，未得到图片链接。"
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_obj = json.loads(err_body)
            msg = err_obj.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        return None, f"【自画像】请求失败：{msg}"
    except Exception as e:
        return None, f"【自画像】生成失败：{e}"


def _selfie_node(state: SelfieState) -> SelfieState:
    """
    自画像子图核心节点：根据用户画像与 query 拼 prompt，调用智谱图像生成 API，写回图片 URL 与说明。

    入参：
    state：SelfieState，当前图状态，含 user_profile、query 等。

    返回值：
    SelfieState：更新后的状态，写入 selfie_placeholder、selfie_image_url、selfie_advice、thinking。

    关键逻辑：
    若 API 调用成功则写入 URL 与友好说明；失败则写入错误说明；并追加 thinking 文案供前端展示。
    """
    new_state: SelfieState = dict(state)
    new_state["selfie_placeholder"] = "selfie"

    # 自画像优先使用 .env 配置（先使用配置），未配置时再回退到 Redis 用户画像；后续扩展用户信息录入后可改为画像优先
    profile = dict(state.get("user_profile") or {})
    profile["age"] = USER_AGE if USER_AGE is not None else profile.get("age")
    profile["gender"] = (USER_SEX or "").strip() or profile.get("gender")
    profile["height_cm"] = USER_HEIGHT if USER_HEIGHT is not None else profile.get("height_cm")
    profile["weight_kg"] = USER_WEIGHT if USER_WEIGHT is not None else profile.get("weight_kg")
    profile["name"] = (USER_NAME or "").strip() or profile.get("name")
    profile["bmi"] = (USER_BMI or "").strip() or profile.get("bmi")
    profile["bmi_category"] = (USER_BMI_CATEGORY or "").strip() or profile.get("bmi_category")

    query = (state.get("query") or "").strip()
    prompt = _build_selfie_prompt(profile, query)

    url, advice = _call_zhipu_image_api(prompt)
    new_state["selfie_advice"] = advice
    if url:
        new_state["selfie_image_url"] = url
        thinking_msg = SELFIE_THINKING_DONE
    else:
        new_state["selfie_image_url"] = ""
        thinking_msg = SELFIE_THINKING_ERROR

    prev_thinking = (new_state.get("thinking") or "").strip()
    parts = [p for p in [prev_thinking, SELFIE_THINKING, thinking_msg] if p]
    new_state["thinking"] = "\n\n".join(parts)

    return new_state


def build_selfie_graph() -> CompiledStateGraph:
    """
    构建自画像子图 StateGraph，单节点：入口 -> _selfie_node -> END。

    入参：
    无入参。

    返回值：
    CompiledStateGraph：编译后的自画像子图，可供总图作为节点调用。

    关键逻辑：
    与 diet、multi_moda 等子图一致，单节点子图，结果通过 state 字段传递给 summary。
    """
    builder: StateGraph[GraphState] = StateGraph(GraphState)
    builder.add_node("selfie_node", _selfie_node)
    builder.set_entry_point("selfie_node")
    builder.add_edge("selfie_node", END)
    return builder.compile()
