# Blueprint de Arquitetura e Engenharia de Sistemas: Paçoca Desktop (Environment Specs)

Este documento estabelece o mapeamento estrutural e a lógica de implementação do ecossistema chroot Debian Trixie, otimizado para integração nativa e aceleração de pipeline gráfico no Android.

## 1. Infraestrutura e Shell (Termux)
*   **Correção do `.bashrc`**: Removidas duplicatas de funções (`claude`), corrigidos erros de sintaxe (chaves extras) e organizadas funções órfãs.
*   **Otimização do Wrapper `bin/debian`**:
    *   Implementado sistema de `trap` para garantir desmontagem segura em caso de fechamento abrupto.
    *   Uso de `umount -l` (lazy) para evitar travamentos de montagem.
    *   Adicionada detecção automática de montagens pendentes antes de iniciar nova sessão.

## 2. O Ciclo do VNC (Fase Inicial)
*   **Instalação**: XFCE4, TigerVNC e D-Bus.
*   **Ajustes de Performance**: Configurado para 16-bit de cor e desativação total de autenticação (`SecurityTypes None`) para fluidez em rede local.
*   **Descoberta mDNS (Avahi)**:
    *   Instalado e configurado `avahi-daemon`.
    *   **Resolução de Conflitos**: Corrigido conflito na porta `5353` com o `mdnsd` nativo do Android.
    *   Ajustado `avahi-daemon.conf` para desativar IPv6 e forçar hostname `pacoca.local`.
*   **Remoção**: A pedido do usuário, todo o ecossistema VNC (servidores, configs e 6 apps Android) foi expurgado para dar lugar à Integração Nativa.

## 3. Integração Nativa (Fase Final - Alta Performance)
*   **Termux-X11**: Implementado como substituto do VNC. Diferente do VNC, o Termux-X11 usa sockets Unix locais, eliminando o overhead de rede TCP.
*   **Gerenciamento de Usuários Android**:
    *   App instalado no usuário principal (`User 0`).
    *   Removido do perfil `Dual App` (`User 95`) para evitar confusão de foco.
*   **Configuração do Display**:
    *   Resolução dinâmica baseada no comando `wm size`.
    *   Orientação forçada para Landscape.
    *   **DPI Ajustado para 320**: Interface redimensionada para legibilidade ideal em telas de alta densidade.
*   **Ponte de Socket (Chroot Fix)**:
    *   Implementada montagem `bind` de `/data/data/com.termux/files/usr/tmp` para `/tmp` dentro do Debian.
    *   Isso permitiu que o Debian "enxergasse" o socket X11 criado pelo Termux, possibilitando a saída de vídeo direta.

## 4. Scripts de Automação criados
*   **`~/bin/debian`**: Gerencia o ciclo de vida do chroot (mount/unmount/enter).
*   **`~/bin/start-native`**: O "botão de ligar" do sistema.
    1. Limpa sessões mortas.
    2. Inicia o servidor Termux-X11 com DPI 320.
    3. Traz o App Android para o primeiro plano.
    4. Garante montagens de socket e inicia o D-Bus.
    5. Lança a `xfce4-session` com exportação correta de `DISPLAY=:1`.

## 5. Estado Atual do Sistema
*   **Usuário**: `pacoca` (Home: `/home/pacoca`).
*   **Interface**: XFCE4 completa.
*   **Display**: Nativo (Termux-X11), sem lag de rede.
*   **DPI**: 320.
*   **Segurança**: Acesso via root restrito ao Termux, sem portas de rede abertas (VNC desativado).

---
*Anotação gerada em 23 de Maio de 2026.*
