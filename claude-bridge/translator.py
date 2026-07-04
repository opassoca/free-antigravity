import json

# Mapeamento de modelos para enganar o Claude Code
MODEL_MAPPING = {
    "claude-3-5-sonnet-20241022": "gemini-1.5-flash",
    "claude-3-5-sonnet": "gemini-1.5-flash",
    "claude-3-5-haiku": "gemini-1.5-flash",
    "claude-3-opus": "gemini-1.5-pro",
}

def anthropic_to_gemini(messages, system=None):
    """Converte o histórico de mensagens da Anthropic para o formato do Gemini."""
    gemini_history = []
    
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # Claude roles: user, assistant
        # Gemini roles: user, model
        gemini_role = "user" if role == "user" else "model"
        
        parts = []
        if isinstance(content, str):
            parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    parts.append({"text": block.get("text")})
                elif block.get("type") == "tool_use":
                    parts.append({
                        "function_call": {
                            "name": block.get("name"),
                            "args": block.get("input")
                        }
                    })
                elif block.get("type") == "tool_result":
                    # Tentativa de converter tool_result
                    # O Gemini espera que isso seja uma resposta a uma function_call anterior
                    parts.append({
                        "function_response": {
                            "name": block.get("tool_use_id").replace("call_", ""), 
                            "response": {"result": block.get("content")}
                        }
                    })
        
        gemini_history.append({"role": gemini_role, "parts": parts})
    
    return gemini_history
