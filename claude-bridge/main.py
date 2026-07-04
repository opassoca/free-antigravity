import os
import json
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import google.generativeai as genai
from translator import anthropic_to_gemini, MODEL_MAPPING

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClaudeBridge")

app = FastAPI()

# Configuração do Gemini via ENV do ANTIGRAVITY-BRIDGE/Switcher
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logger.warning("GEMINI_API_KEY não encontrada nas variáveis de ambiente.")

@app.post("/v1/messages")
async def messages_proxy(request: Request):
    body = await request.json()
    
    anthropic_messages = body.get("messages", [])
    system_prompt = body.get("system", None)
    stream = body.get("stream", False)
    requested_model = body.get("model", "claude-3-5-sonnet")
    
    # Mapeamento para o motor do Google
    gemini_model_name = MODEL_MAPPING.get(requested_model, "gemini-1.5-flash")
    logger.info(f"Proxying {requested_model} -> {gemini_model_name} (Stream: {stream})")
    
    # Tradução do Histórico
    gemini_history = anthropic_to_gemini(anthropic_messages)
    last_msg = gemini_history.pop()
    
    # Inicialização do Modelo (Evitando erro de system_instruction vazia)
    model_kwargs = {"model_name": gemini_model_name}
    if system_prompt:
        model_kwargs["system_instruction"] = system_prompt
        
    model = genai.GenerativeModel(**model_kwargs)
    chat = model.start_chat(history=gemini_history)
    
    if not stream:
        try:
            response = chat.send_message(last_msg["parts"])
            return {
                "id": f"msg_{response.usage_metadata.prompt_token_count}",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": response.text}],
                "model": requested_model,
                "usage": {
                    "input_tokens": response.usage_metadata.prompt_token_count,
                    "output_tokens": response.usage_metadata.candidates_token_count
                }
            }
        except Exception as e:
            logger.error(f"Erro no Gemini: {e}")
            return {"error": {"type": "api_error", "message": str(e)}}
    else:
        async def event_generator():
            try:
                # Eventos iniciais padrão Anthropic
                yield f"data: {json.dumps({'type': 'message_start', 'message': {'id': 'proxy_msg', 'type': 'message', 'role': 'assistant', 'model': requested_model, 'content': [], 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
                yield f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
                
                # Execução via Stream
                response = chat.send_message(last_msg["parts"], stream=True)
                for chunk in response:
                    if chunk.text:
                        yield f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': chunk.text}})}\n\n"
                
                yield f"data: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
                yield f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 0}})}\n\n"
                yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"
            except Exception as e:
                logger.error(f"Erro no stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': str(e)}})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Rodando em 127.0.0.1 para evitar exposição externa não autorizada
    uvicorn.run(app, host="127.0.0.1", port=8082, log_level="info")
