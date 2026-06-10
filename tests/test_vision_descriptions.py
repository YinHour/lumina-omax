import asyncio
import json

from open_notebook.graphs.source import (
    FigureContext,
    _build_excel_context_from_anchor,
    _invoke_vision_with_retries,
    _is_transient_vision_error,
    _render_vision_result,
    _safe_figure_description,
    _structured_vision_description,
    _trim_excel_empty_table_rows,
    _vision_model_inference_kwargs,
)


def test_structured_vision_description_renders_confirmed_and_uncertain_items():
    raw = json.dumps(
        {
            "image_type": "hpht_curve",
            "readability": "high",
            "confidence": 0.86,
            "confirmed_facts": ["绿色坐标轴标注为温度(℃)", "蓝色坐标轴标注为稠度(Bc)"],
            "extracted_values": [{"name": "稠化时间", "value": "276 min"}],
            "uncertain_items": ["底部小表格局部文字不可读取"],
            "domain_interpretation": "该曲线可作为样品稠化行为的证据。",
        },
        ensure_ascii=False,
    )

    result = _structured_vision_description(raw)
    rendered = _render_vision_result(
        "curve.jpg",
        result,
        FigureContext(filename="curve.jpg", source_kind="pdf", page=1),
    )

    assert "图像类型：hpht_curve" in rendered
    assert "置信度：0.86" in rendered
    assert "绿色坐标轴标注为温度(℃)" in rendered
    assert "稠化时间：276 min" in rendered
    assert "底部小表格局部文字不可读取" in rendered


def test_structured_vision_description_rejects_prompt_leakage():
    raw = json.dumps(
        {
            "image_type": "lab_photo",
            "readability": "high",
            "confidence": 0.91,
            "confirmed_facts": ["必须遵守的规则：不输出推理过程"],
            "extracted_values": [],
            "uncertain_items": [],
            "domain_interpretation": "CRITICAL RULES - VIOLATION MEANS FAILURE",
        },
        ensure_ascii=False,
    )

    result = _structured_vision_description(raw)

    assert not result.accepted
    assert "prompt_leakage" in result.rejection_reasons


def test_safe_figure_description_replaces_rejected_output_with_safe_description():
    raw = "让我们仔细看这张图。绿色可能是温度，或者是稠度。"

    description = _safe_figure_description(
        "bad.jpg",
        raw,
        FigureContext(filename="bad.jpg", source_kind="pdf", page=2),
    )

    assert "图像类型：unknown" in description
    assert "描述级别：context_only" in description
    assert "图片内容未能稳定识别" in description
    assert "质量提示" not in description
    assert "reasoning_leakage" not in description
    assert "让我们" not in description
    assert "可能是温度" not in description


def test_safe_figure_description_always_returns_minimum_description():
    description = _safe_figure_description(
        "blank.jpg",
        "",
        FigureContext(filename="blank.jpg", source_kind="pdf", width=80, height=40),
    )

    assert "图像类型：unknown" in description
    assert "图片较小，以下描述可信度不高" in description
    assert "invalid_json" not in description
    assert "质量提示" not in description
    assert "图片描述未通过质量校验" not in description


def test_large_image_fallback_does_not_claim_image_is_small():
    description = _safe_figure_description(
        "large.png",
        "",
        FigureContext(filename="large.png", source_kind="excel", width=897, height=658),
    )

    assert "图片较小" not in description
    assert "模型未能稳定识别该图片内容" in description
    assert "图片尺寸：897x658px" in description


def test_safe_figure_description_keeps_structured_non_json_trend_description():
    raw = """图像类型：hpht_curve
可确认信息：
- 该图为高温高压稠化仪曲线图。
- 绿色和红色曲线整体呈上升趋势，蓝色曲线保持低位波动。
无法确认：
- 图片分辨率较低，无法可靠读取具体稠化时间。"""

    description = _safe_figure_description(
        "curve.jpg",
        raw,
        FigureContext(filename="curve.jpg", source_kind="pdf", width=320, height=156),
    )

    assert "图像类型：hpht_curve" in description
    assert "描述级别：trend_only" in description
    assert "绿色和红色曲线整体呈上升趋势" in description
    assert "图片描述未通过质量校验" not in description


def test_safe_figure_description_uses_context_for_table_or_photo_fallback():
    raw = "实验照片显示浆杯和搅拌叶片，水泥浆附着在叶片表面。"
    context = FigureContext(
        filename="photo.jpg",
        source_kind="pdf",
        table_row_text="合成小样220801② | 0.8 | 包芯1指半，曲线正常，底部1cm沉死",
        width=147,
        height=225,
    )

    description = _safe_figure_description("photo.jpg", raw, context)

    assert "图像类型：lab_photo" in description
    assert "描述级别：visual_state_only" in description
    assert "浆杯和搅拌叶片" in description
    assert "包芯1指半" in description
    assert "图片描述未通过质量校验" not in description


def test_low_readability_keeps_description_but_drops_unreliable_values():
    raw = json.dumps(
        {
            "image_type": "hpht_curve",
            "readability": "low",
            "confidence": 0.68,
            "description_level": "trend_only",
            "confirmed_facts": ["图中包含三条随时间变化的曲线。"],
            "extracted_values": [{"name": "稠化时间", "value": "100 min"}],
            "uncertain_items": ["图片分辨率较低，无法可靠读取具体数值。"],
            "domain_interpretation": "该曲线可用于判断稠化趋势。",
        },
        ensure_ascii=False,
    )

    description = _safe_figure_description(
        "curve.jpg",
        raw,
        FigureContext(filename="curve.jpg", source_kind="pdf"),
    )

    assert "图像类型：hpht_curve" in description
    assert "图中包含三条随时间变化的曲线" in description
    assert "稠化时间：100 min" not in description
    assert "unreliable_extracted_values" not in description
    assert "质量提示" not in description


def test_fallback_filters_broken_json_fragments_from_user_output():
    raw = """
{
  "image_type": "embedded_table_or_screenshot",
  "readability": "medium",
  "confidence": 0.88,
  "description_level": "context_only",
  "confirmed_facts": [
    "表格中包含空白实验和合成小样两组数据",
    "右侧嵌入稠化曲线和实物照片"
"""

    description = _safe_figure_description(
        "table.jpg",
        raw,
        FigureContext(filename="table.jpg", source_kind="pdf"),
    )

    assert "图像类型：embedded_table_or_screenshot" in description
    assert "表格中包含空白实验和合成小样两组数据" in description
    assert '"image_type"' not in description
    assert '"confirmed_facts"' not in description
    assert "{" not in description


def test_excel_anchor_context_uses_sheet_row_and_headers():
    rows = [
        ["样品编号", "流变值", "稳定性", "备注", "照片"],
        ["FS-13L", "270/149/104/56/4/4", "0.04", "温度压力轻微波动", ""],
    ]

    context = _build_excel_context_from_anchor(rows, "稳定性测试", "E2", "excel_img_001.png")

    assert context.source_kind == "excel"
    assert context.sheet_name == "稳定性测试"
    assert context.cell_anchor == "稳定性测试!E2"
    assert context.table_headers == ["样品编号", "流变值", "稳定性", "备注", "照片"]
    assert "FS-13L" in context.table_row_text
    assert "温度压力轻微波动" in context.table_row_text


def test_excel_anchor_context_keeps_image_dimensions():
    context = _build_excel_context_from_anchor(
        [["项目", "结果"], ["高温稳定性", "7d"]],
        "稳定性测试",
        "B2",
        "excel_img_002.png",
        width=897,
        height=658,
    )

    assert context.width == 897
    assert context.height == 658


def test_trim_excel_empty_table_rows_removes_blank_rows_only():
    markdown = """# Sheet: 示例

| 项目 | 结果 |
| --- | --- |
| 密度 | 2.04 |
|  |  |
|   |   |

# Sheet: 第二页

| 项目 | 结果 |
| --- | --- |
| 强度 | 2.82 |
"""

    trimmed = _trim_excel_empty_table_rows(markdown)

    assert "|  |  |" not in trimmed
    assert "|   |   |" not in trimmed
    assert "| --- | --- |" in trimmed
    assert "| 密度 | 2.04 |" in trimmed
    assert "| 强度 | 2.82 |" in trimmed


def test_vision_model_kwargs_use_ollama_options_for_ollama(monkeypatch):
    monkeypatch.setenv("VISION_NUM_CTX", "2048")
    monkeypatch.setenv("VISION_NUM_PREDICT", "384")
    monkeypatch.setenv("VISION_TEMPERATURE", "0")
    monkeypatch.setenv("VISION_MAX_TOKENS", "999")

    kwargs = _vision_model_inference_kwargs("ollama")

    assert kwargs == {
        "num_ctx": 2048,
        "num_predict": 384,
        "temperature": 0.0,
    }


def test_vision_model_kwargs_avoid_ollama_options_for_other_providers(monkeypatch):
    monkeypatch.setenv("VISION_NUM_CTX", "2048")
    monkeypatch.setenv("VISION_NUM_PREDICT", "384")
    monkeypatch.setenv("VISION_TEMPERATURE", "0")
    monkeypatch.setenv("VISION_MAX_TOKENS", "384")

    kwargs = _vision_model_inference_kwargs("openai_compatible")

    assert kwargs == {
        "max_tokens": 384,
        "temperature": 0.0,
    }
    assert "num_ctx" not in kwargs
    assert "num_predict" not in kwargs


def test_transient_vision_error_detects_minimax_520():
    error = Exception(
        "Error code: 500 - {'type': 'error', 'error': {'type': 'server_error', "
        "'message': 'unknown error, 520 (1000)', 'http_code': '500'}}"
    )

    assert _is_transient_vision_error(error)


def test_invoke_vision_with_retries_recovers_after_transient_failure(monkeypatch):
    monkeypatch.setenv("VISION_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("VISION_MAX_RETRIES", "2")
    monkeypatch.setenv("VISION_RETRY_BASE_DELAY_SECONDS", "0")
    attempts = 0

    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception("unknown error, 520 (1000)")
        return "ok"

    result = asyncio.run(_invoke_vision_with_retries(flaky_call))

    assert result == "ok"
    assert attempts == 2


def test_invoke_vision_with_retries_times_out_and_stops(monkeypatch):
    monkeypatch.setenv("VISION_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setenv("VISION_MAX_RETRIES", "1")
    monkeypatch.setenv("VISION_RETRY_BASE_DELAY_SECONDS", "0")
    attempts = 0

    async def hanging_call():
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(1)
        return "never"

    try:
        asyncio.run(_invoke_vision_with_retries(hanging_call))
    except TimeoutError:
        pass
    else:
        raise AssertionError("Expected TimeoutError")

    assert attempts == 2
