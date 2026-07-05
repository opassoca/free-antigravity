import os
import sys
import uvicorn

# Adicionar o diretorio raiz do script ao sys.path para garantir que os modulos locais sejam localizados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Importar o app da API modularizada
from api.routes import app

if __name__ == "__main__":
    # Rodar localmente na porta 8084
    uvicorn.run(app, host="127.0.0.1", port=8084, log_level="info")
