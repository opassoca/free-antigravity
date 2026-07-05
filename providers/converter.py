"""Request format converters: Gemini <-> OpenAI.

Translates request payloads between the Gemini API format (used by agy CLI)
and the OpenAI Chat Completions format (used by most AI providers).
"""

import json

from loguru import logger


def convert_gemini_to_openai(gemini_request: dict, target_model: str) -> dict:
    """Convert a Gemini API request to OpenAI Chat Completions format.

    Args:
        gemini_request: The original request body from the agy CLI.
        target_model: The resolved model name for the provider.

    Returns:
        OpenAI-compatible request payload.
    """
    openai_messages = []

    # 1. Traduzir o historico de mensagens (contents)
    contents = gemini_request.get("contents", [])
    for content in contents:
        role = content.get("role")
        openai_role = "user" if role == "user" else "assistant"

        parts = content.get("parts", [])
        text_content = ""
        tool_calls = []

        for part in parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                fcall = part["functionCall"]
                tool_calls.append({
                    "id": fcall.get("name"),
                    "type": "function",
                    "function": {
                        "name": fcall.get("name"),
                        "arguments": json.dumps(fcall.get("args", {})),
                    },
                })
            elif "functionResponse" in part:
                fresp = part["functionResponse"]
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": fresp.get("name"),
                    "content": json.dumps(fresp.get("response", {})),
                })

        if text_content or tool_calls:
            msg: dict = {"role": openai_role}
            if text_content:
                msg["content"] = text_content
            if tool_calls:
                msg["tool_calls"] = tool_calls
            openai_messages.append(msg)

    # 2. Traduzir as declaracoes de ferramentas (tools)
    openai_tools = []
    if "tools" in gemini_request:
        for tool_group in gemini_request["tools"]:
            if "functionDeclarations" in tool_group:
                for decl in tool_group["functionDeclarations"]:
                    params = decl.get("parameters", {}).copy()
                    _normalize_json_schema_types(params)

                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": decl.get("name"),
                            "description": decl.get("description", ""),
                            "parameters": params,
                        },
                    })

    # 3. Construir o corpo final para a OpenAI
    openai_payload: dict = {
        "model": target_model,
        "messages": openai_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if openai_tools:
        openai_payload["tools"] = openai_tools

    # 4. Mapear configuracoes extras de geracao
    gen_config = gemini_request.get("generationConfig", {})
    if "temperature" in gen_config:
        openai_payload["temperature"] = gen_config["temperature"]
    if "maxOutputTokens" in gen_config:
        openai_payload["max_tokens"] = gen_config["maxOutputTokens"]
    if "topP" in gen_config:
        openai_payload["top_p"] = gen_config["topP"]
    if "stopSequences" in gen_config:
        openai_payload["stop"] = gen_config["stopSequences"]

    return openai_payload


def convert_openai_chunk_to_gemini(chunk_json: dict) -> dict | None:
    """Convert an OpenAI SSE chunk to Gemini streaming format.

    Args:
        chunk_json: Parsed JSON from an OpenAI SSE data line.

    Returns:
        Gemini-formatted chunk dict, or None if chunk should be skipped.
    """
    choices = chunk_json.get("choices", [])
    if not choices:
        return None

    delta = choices[0].get("delta", {})
    finish_reason = choices[0].get("finish_reason")

    # Texto normal ou reasoning
    text_content = delta.get("content", "")
    reasoning = delta.get("reasoning_content", "")
    if reasoning:
        text_content = reasoning

    if text_content:
        return {
            "candidates": [{
                "content": {
                    "role": "model",
                    "parts": [{"text": text_content}],
                },
            }],
        }

    # Tool calls
    tool_calls = delta.get("tool_calls", [])
    if tool_calls:
        parts = []
        for tc in tool_calls:
            func = tc.get("function", {})
            if func.get("name"):
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                parts.append({
                    "functionCall": {
                        "name": func["name"],
                        "args": args,
                    },
                })
        if parts:
            return {
                "candidates": [{
                    "content": {
                        "role": "model",
                        "parts": parts,
                    },
                }],
            }

    # Finish reason
    if finish_reason:
        gemini_reason = _map_finish_reason(finish_reason)
        return {
            "candidates": [{
                "finishReason": gemini_reason,
                "content": {
                    "role": "model",
                    "parts": [{"text": ""}],
                },
            }],
        }

    return None


def _normalize_json_schema_types(schema: dict) -> None:
    """Recursively lowercase JSON Schema type fields for OpenAI compat."""
    if not isinstance(schema, dict):
        return
    if "type" in schema:
        schema["type"] = schema["type"].lower()
    if "properties" in schema:
        for v in schema["properties"].values():
            _normalize_json_schema_types(v)
    if "items" in schema:
        _normalize_json_schema_types(schema["items"])


def _map_finish_reason(openai_reason: str) -> str:
    """Map OpenAI finish_reason to Gemini finishReason."""
    mapping = {
        "stop": "STOP",
        "length": "MAX_TOKENS",
        "content_filter": "SAFETY",
        "tool_calls": "STOP",
        "function_call": "STOP",
    }
    return mapping.get(openai_reason, "OTHER")
