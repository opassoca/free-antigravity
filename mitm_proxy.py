#!/usr/bin/env python3
"""
Free Antigravity MITM Proxy

Proxy MITM auxiliar que intercepta chamadas HTTPS do binario agy para
www.googleapis.com e as redireciona para o servidor FastAPI local (porta 8084).

Para outros dominios, atua como proxy CONNECT transparente.

Uso: python3 mitm_proxy.py
  - Roda na porta 8085 por padrao
  - Gera certificados CA auto-assinados em data/certs/
  - O wrapper free-antigravity configura HTTPS_PROXY=http://127.0.0.1:8085
"""

import os
import ssl
import socket
import subprocess
import threading
import json
import http.client

CERT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "certs")
FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8084
MITM_PORT = 8085

# Dominios que devemos interceptar e mockar
INTERCEPTED_HOSTS = {"www.googleapis.com", "googleapis.com", "oauth2.googleapis.com"}

# Contexto SSL cacheado
_SSL_CONTEXT = None


def generate_certificates():
    """Gera CA e certificado do servidor para www.googleapis.com."""
    os.makedirs(CERT_DIR, exist_ok=True)
    ca_key = os.path.join(CERT_DIR, "ca.key")
    ca_crt = os.path.join(CERT_DIR, "ca.crt")
    server_key = os.path.join(CERT_DIR, "server.key")
    server_csr = os.path.join(CERT_DIR, "server.csr")
    server_crt = os.path.join(CERT_DIR, "server.crt")
    ext_file = os.path.join(CERT_DIR, "v3.ext")

    if not os.path.exists(ca_crt):
        print("[MITM] Gerando chave CA...")
        subprocess.run(
            ["openssl", "genrsa", "-out", ca_key, "2048"],
            check=True, capture_output=True,
        )
        print("[MITM] Gerando certificado CA...")
        subprocess.run(
            [
                "openssl", "req", "-new", "-x509", "-days", "3650",
                "-key", ca_key, "-out", ca_crt,
                "-subj", "/CN=Free Antigravity Mock CA",
            ],
            check=True, capture_output=True,
        )

    if not os.path.exists(server_crt):
        print("[MITM] Gerando chave do servidor...")
        subprocess.run(
            ["openssl", "genrsa", "-out", server_key, "2048"],
            check=True, capture_output=True,
        )
        print("[MITM] Gerando CSR do servidor...")
        subprocess.run(
            [
                "openssl", "req", "-new", "-key", server_key, "-out", server_csr,
                "-subj", "/CN=www.googleapis.com",
            ],
            check=True, capture_output=True,
        )

        with open(ext_file, "w") as f:
            f.write(
                "authorityKeyIdentifier=keyid,issuer\n"
                "basicConstraints=CA:FALSE\n"
                "keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment\n"
                "subjectAltName = @alt_names\n\n"
                "[alt_names]\n"
                "DNS.1 = www.googleapis.com\n"
                "DNS.2 = googleapis.com\n"
                "DNS.3 = *.googleapis.com\n"
            )

        print("[MITM] Assinando certificado do servidor...")
        subprocess.run(
            [
                "openssl", "x509", "-req", "-in", server_csr,
                "-CA", ca_crt, "-CAkey", ca_key, "-CAcreateserial",
                "-out", server_crt, "-days", "3650", "-extfile", ext_file,
            ],
            check=True, capture_output=True,
        )

    print(f"[MITM] Certificados prontos em {CERT_DIR}")
    return ca_crt


def get_ssl_context():
    """Retorna o contexto SSL para conexoes interceptadas (carregado uma unica vez)."""
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        _SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        _SSL_CONTEXT.load_cert_chain(
            certfile=os.path.join(CERT_DIR, "server.crt"),
            keyfile=os.path.join(CERT_DIR, "server.key"),
        )
    return _SSL_CONTEXT


def pipe_sockets(src, dst):
    """Copia dados de src para dst ate EOF."""
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass


def read_http_request(sock):
    """Le uma requisicao HTTP completa de um socket."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk

    if b"\r\n\r\n" not in data:
        return None, None, None, b""

    header_end = data.index(b"\r\n\r\n")
    header_bytes = data[:header_end]
    body_start = data[header_end + 4:]

    lines = header_bytes.decode("utf-8", errors="ignore").split("\r\n")
    request_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    parts = request_line.split(" ")
    method = parts[0] if len(parts) >= 1 else "GET"
    path = parts[1] if len(parts) >= 2 else "/"

    # Ler corpo restante se content-length estiver presente
    content_length = int(headers.get("content-length", 0))
    body = body_start
    while len(body) < content_length:
        chunk = sock.recv(4096)
        if not chunk:
            break
        body += chunk

    return method, path, headers, body


def build_mock_response(method, path, headers):
    """Gera resposta mockada para chamadas interceptadas ao googleapis.com."""
    # Redirecionar para o FastAPI local
    try:
        conn = http.client.HTTPConnection(FASTAPI_HOST, FASTAPI_PORT, timeout=5)
        fwd_headers = {"Content-Type": "application/json"}
        if "authorization" in headers:
            fwd_headers["Authorization"] = headers["authorization"]
        conn.request(method, path, headers=fwd_headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        resp_status = resp.status
        resp_reason = resp.reason
        resp_headers = dict(resp.getheaders())
        conn.close()
    except Exception as e:
        resp_body = json.dumps({"error": f"MITM forward error: {e}"}).encode("utf-8")
        resp_status = 500
        resp_reason = "Internal Server Error"
        resp_headers = {"Content-Type": "application/json"}

    # Construir resposta HTTP
    response = f"HTTP/1.1 {resp_status} {resp_reason}\r\n"
    for k, v in resp_headers.items():
        if k.lower() not in ("transfer-encoding", "content-length"):
            response += f"{k}: {v}\r\n"
    response += f"Content-Length: {len(resp_body)}\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    return response.encode("utf-8") + resp_body


def handle_intercepted(client_sock, host):
    """Intercepta conexao TLS para dominios mockados."""
    # Responder com 200 Connection Established
    # (o header CONNECT ja foi lido pelo caller)

    # Fazer upgrade TLS com certificado falso usando o contexto cacheado
    ssl_ctx = get_ssl_context()

    try:
        tls_sock = ssl_ctx.wrap_socket(client_sock, server_side=True)
    except ssl.SSLError as e:
        print(f"[MITM] SSL handshake falhou para {host}: {e}")
        client_sock.close()
        return

    try:
        method, path, headers, body = read_http_request(tls_sock)
        if method is None:
            tls_sock.close()
            return

        print(f"[MITM] Interceptado: {method} {path} -> FastAPI local")
        response = build_mock_response(method, path, headers)
        tls_sock.sendall(response)
    except Exception as e:
        print(f"[MITM] Erro ao processar requisicao interceptada: {e}")
    finally:
        try:
            tls_sock.close()
        except Exception:
            pass


def handle_transparent(client_sock, host, port):
    """Proxy CONNECT transparente para dominios nao-interceptados."""
    try:
        remote_sock = socket.create_connection((host, port), timeout=10)
    except Exception as e:
        err_msg = f"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"
        client_sock.sendall(err_msg.encode("utf-8"))
        client_sock.close()
        return

    # Pipear trafego nos dois sentidos
    t1 = threading.Thread(target=pipe_sockets, args=(client_sock, remote_sock), daemon=True)
    t2 = threading.Thread(target=pipe_sockets, args=(remote_sock, client_sock), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    try:
        client_sock.close()
    except Exception:
        pass
    try:
        remote_sock.close()
    except Exception:
        pass


def handle_client(client_sock, addr):
    """Handler principal para cada conexao ao proxy."""
    try:
        # Ler a primeira linha (esperamos CONNECT host:port HTTP/1.x)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = client_sock.recv(4096)
            if not chunk:
                client_sock.close()
                return
            data += chunk

        first_line = data.split(b"\r\n")[0].decode("utf-8", errors="ignore")
        parts = first_line.strip().split()

        if len(parts) < 2:
            client_sock.close()
            return

        method = parts[0].upper()

        if method == "CONNECT":
            target = parts[1]
            if ":" in target:
                host, port_str = target.rsplit(":", 1)
                port = int(port_str)
            else:
                host = target
                port = 443

            if host in INTERCEPTED_HOSTS:
                # Enviar 200 e interceptar
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                handle_intercepted(client_sock, host)
            else:
                # Proxy transparente
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                handle_transparent(client_sock, host, port)
        else:
            # Requisicao HTTP normal (nao-CONNECT) — não suportada aqui
            err = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n"
            client_sock.sendall(err)
            client_sock.close()

    except Exception as e:
        print(f"[MITM] Erro no handler: {e}")
        try:
            client_sock.close()
        except Exception:
            pass


def install_ca_cert(ca_crt_path):
    """Cria um bundle de certificados local mesclando o CA do sistema com o nosso CA."""
    custom_bundle = os.path.join(CERT_DIR, "ca-bundle.crt")
    
    cert_locations = [
        "/data/data/com.termux/files/usr/glibc/etc/ssl/certs/ca-certificates.crt",
        "/data/data/com.termux/files/usr/glibc/etc/pki/tls/certs/ca-bundle.crt",
        "/data/data/com.termux/files/usr/etc/tls/cert.pem",
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
    ]
    
    ca_pem = open(ca_crt_path, "r").read()
    marker = "# Free Antigravity Mock CA"
    
    # Encontrar o primeiro cert store do sistema valido
    system_certs = ""
    for cert_file in cert_locations:
        if os.path.exists(cert_file):
            try:
                with open(cert_file, "r") as f:
                    system_certs = f.read()
                print(f"[MITM] Base de certificados importada de {cert_file}")
                break
            except Exception as e:
                print(f"[MITM] Nao foi possivel ler {cert_file}: {e}")
                
    # Salvar o bundle customizado na pasta de certificados do proxy
    try:
        with open(custom_bundle, "w") as f:
            f.write(system_certs)
            f.write(f"\n{marker}\n{ca_pem}\n")
        print(f"[MITM] Bundle customizado criado com sucesso em {custom_bundle}")
        return True
    except Exception as e:
        print(f"[MITM] Erro ao salvar bundle customizado: {e}")
        return False


def main():
    ca_crt = generate_certificates()
    install_ca_cert(ca_crt)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", MITM_PORT))
    server.listen(128)
    print(f"[MITM] Proxy MITM rodando em 127.0.0.1:{MITM_PORT}")

    try:
        while True:
            client_sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("[MITM] Encerrando proxy MITM...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
