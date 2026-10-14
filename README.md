# claude-multi-accounts-for-macos

Para quem usa **mais de uma conta do Claude** no mesmo Mac (por exemplo, uma pessoal e uma do trabalho) e troca de conta quando o limite de uma acaba.

- **Sessões compartilhadas no Claude Desktop.** Trocou de conta, as sessões da aba Code continuam lá, com o histórico completo. Criar, arquivar ou apagar uma sessão vale para todas as contas.
- **Limites de todas as contas no menu bar.** Uso da sessão (5 h) e do semanal de cada conta, lado a lado, com barras e horário de reinício.

> Não é uma ferramenta oficial da Anthropic. Ela mexe em arquivos internos do Claude Desktop e usa um endpoint não documentado, então pode parar de funcionar numa atualização do app. Se uma das contas for da sua empresa, confira se a política dela permite esse uso.

## Instalar

```bash
curl -fsSL https://raw.githubusercontent.com/NicolasEymael/claude-multi-accounts-for-macos/main/install.sh | bash
```

Requisitos: macOS, Command Line Tools (`xcode-select --install`) e, para o menu bar, [Homebrew](https://brew.sh) (o instalador usa para instalar o [SwiftBar](https://swiftbar.app)).

O medidor do menu bar lê os logins do **Claude Code no terminal**. Se você só fez login no app, entre também no CLI, um diretório de configuração por conta:

```bash
claude                                      # conta 1 (padrão, ~/.claude) → /login
CLAUDE_CONFIG_DIR=~/.claude-trabalho claude # conta 2 → /login
```

Depois de logar uma conta nova, rode `~/.claude-multi-accounts/install.sh --reconfigure`.

Na primeira leitura, o macOS pode perguntar se o `security` pode acessar o item "Claude Code-credentials" do Keychain: escolha **Permitir sempre**.

## Usar

1. No Claude Desktop, saia da conta atual e entre na outra. As sessões já estão lá.
2. Abra uma sessão e mande a mensagem. A primeira mensagem na conta nova reprocessa o contexto inteiro, então gasta mais que as seguintes.

No menu bar, cada conta aparece como uma letra com duas barrinhas: **sessão em cima, semanal embaixo**. Azul é normal, laranja a partir de 70 %, vermelho a partir de 90 %. Clique para ver o detalhe.

Para trocar a letra ou o nome de uma conta, edite `~/.claude-multi-accounts/accounts.json`.

## Como funciona

**Sessões.** O histórico de cada conversa fica em `~/.claude/projects/` e não depende de conta. O que é por conta é a lista da aba Code, em `~/Library/Application Support/Claude/claude-code-sessions/<conta>/<organização>/`. Um agente do `launchd` espelha essa lista entre as pastas de todas as contas: a cada mudança e a cada 30 s, o arquivo mais novo vence. Só a pasta da conta ativa muda, então a das outras já está em dia quando você troca.

- Sessão apagada numa conta sai das outras; o arquivo vai para `~/.claude-multi-accounts/trash/`, nunca é apagado de vez.
- Backup diário de toda a pasta em `~/.claude-multi-accounts/backups/` (mantém 7).
- Tarefas agendadas (`scheduled-tasks.json`) continuam separadas por conta.

**Menu bar.** Um plugin do SwiftBar lê o token de cada conta do Claude Code no Keychain (sem exibir nem gravar o token) e consulta o mesmo endpoint de uso que o `/usage` mostra, a cada 5 min. O endpoint limita consultas seguidas; quando isso acontece, o menu mostra a última leitura com o horário dela. O token do CLI expira em 8 h: quando expira, o plugin pede ao próprio `claude` para renovar com uma chamada mínima ao Haiku (no máximo uma vez a cada 30 min por conta). Para desligar isso, use `"auto_renew": false` no `accounts.json`.

Conectores do claude.ai são por organização: uma sessão criada numa conta abre na outra sem os conectores da primeira.

## Arquivos

| Onde | O quê |
|---|---|
| `~/.claude-multi-accounts/bin/` | scripts |
| `~/.claude-multi-accounts/accounts.json` | contas do menu bar |
| `~/.claude-multi-accounts/logs/session-sync.log` | tudo o que o sync copiou ou apagou |
| `~/Library/LaunchAgents/com.github.claude-multi-accounts.session-sync.plist` | agente do sync |

Para simular o sync sem mudar nada: `/usr/bin/python3 ~/.claude-multi-accounts/bin/session-sync.py --dry-run`.

## Desinstalar

```bash
~/.claude-multi-accounts/uninstall.sh          # mantém logs e backups
~/.claude-multi-accounts/uninstall.sh --purge  # apaga tudo
```

As cópias de sessão já feitas continuam no Claude Desktop, sem efeito colateral. O SwiftBar não é removido.

## Dica

O Claude Code apaga históricos com mais de 30 dias. Para manter sessões antigas, adicione `"cleanupPeriodDays": 3650` em `~/.claude/settings.json`.

## Licença

MIT
