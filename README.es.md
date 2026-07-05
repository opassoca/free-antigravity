# 🌌 Free Antigravity — Proxy de IA Unificado de Gravedad Cero

🌎 **Seleccione su idioma:**
[English](README.md) | [Português](README.pt-BR.md) | [Español](README.es.md) | [Русский](README.ru.md) | [中文](README.zh.md)

---

Un proxy unificado de alto rendimiento diseñado para conectar **Antigravity CLI (agy)** y **Claude Code** a cualquier proveedor de IA (Nvidia NIM, OpenRouter, DeepSeek, Mistral, Groq, Ollama) con resolución dinámica de claves y un panel interactivo con física de gravedad cero.

---

## ⚡ Características

*   **Arquitectura de Proxy Unificada:** Atiende tanto las solicitudes de Antigravity CLI `/v1internal` como las de Claude Code `/v1/messages` en un único puerto local (`8084`).
*   **Motor Multi-Proveedor:** Integración dinámica con Nvidia NIM, OpenRouter, DeepSeek nativo, Mistral AI, Groq e instancias locales de Ollama.
*   **Cabeceras Dinámicas de Solicitud:** Cambie el modelo y el proveedor sobre la marcha formateando sus claves de API como `SU_CLAVE:PROVEEDOR/MODELO`.
*   **Página de Inicio Interactiva con Gravedad Cero:** Un panel premium inspirado en Google que ejecuta **física 2D de Matter.js** donde las letras de la marca y las tarjetas flotan libremente y reaccionan al puntero del mouse.

---

## 🚀 Inicio Rápido

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/opassoca/free-antigravity.git
    cd free-antigravity
    ```
2.  **Configurar variables de entorno:**
    Copie el archivo `.env.example` (de la carpeta `free-claude-code`) y complételo con sus claves de proveedor.
3.  **Ejecutar el Servidor:**
    ```bash
    python free-antigravity.py
    ```
4.  **Acceder al Panel:**
    Abra `http://localhost:8084` en su navegador.

---

## 🛠️ Detalles de Configuración

### Formato de Cabecera Dinámica de Clave API
Formatee su token de autenticación para cambiar de backend dinámicamente:
```text
x-api-key: SU_TOKEN_API:nvidia/deepseek-ai/deepseek-r1
x-api-key: SU_TOKEN_API:openrouter/google/gemini-2.5-pro
```

---


## 📱 Ejecución Nativa en Termux
Específicamente optimizado para Termux en Android. Instale los paquetes y ejecute el servidor proxy unificado fácilmente:
```bash
pkg install python ndk-sysroot clang
pip install -r requirements.txt
./install.sh
```

## 👨‍💻 Créditos
Desarrollado con 💙 por [Paçoca (@opassoca)](https://github.com/opassoca).
