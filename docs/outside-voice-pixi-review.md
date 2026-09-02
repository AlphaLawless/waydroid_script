# Voz externa — desafio independente ao plano da migração pixi

Gerado em 2026-09-02 por `/plan-eng-review`, seção *Outside Voice*.
Executor: subagente Claude com contexto limpo (o Codex CLI não está instalado nesta máquina).
**Ressalva honesta:** contexto novo, mas **mesma família de modelo**. Não é leitura de modelo externo.
Para uma voz de fora de verdade: `npm install -g @openai/codex`.

O agente recebeu o design doc, a triagem do upstream e a lista das 9 decisões já tomadas na
revisão de engenharia, com instrução de não repetir a revisão e sim achar o que ela deixou passar.

Reproduzido na íntegra. As verificações que **eu** rodei depois estão marcadas ao final.

---

## 1. Todo o edifício de propagação de PATH é desnecessário. Chame os binários por caminho absoluto.

A escalada A → B → C do design inteiro repousa numa suposição que nunca é declarada, muito menos
examinada: **a de que `lzip` e `tar` precisam ser encontrados via `PATH`.**

Não precisam. Há exatamente dois call sites (`stuff/gapps.py:126,147`), ambos
`run(["tar", "--lzip", ...])`. Troque para `os.path.join(sys.prefix, "bin", "tar")` e:

- `_elevated_path()` — deletado.
- A regressão de sbin (o achado do round 3, a seção mais longa do doc) — nunca existe.
- OQ-SECUREPATH — irrelevante.
- A nota de segurança sobre derrotar o `env_reset` — irrelevante, nada é propagado.
- A checagem de prefixo em `_ENV_REQUIRED` do `check_system_deps()` — vira `os.path.exists()`.
- Critério 13 (ponta a ponta em Debian, o único critério que o CachyOS não exercita) — irrelevante.
- O probe do Assignment — irrelevante.

E a garantia fica *mais forte*: caminho absoluto não pode ser derrotado por PATH nenhum, enquanto o
desenho atual apenas providencia que o PATH provavelmente esteja certo. A razão declarada para
descartar a Approach A ("deixa a falha de PATH acontecer em silêncio") fica vazia quando PATH
deixa de ser o mecanismo.

Com isso, `check_root()` também não precisa de inversão. O README vira:

```
pixi install
sudo .pixi/envs/default/bin/python main.py install gapps
```

O `secure_path` do sudo fica intacto, então `e2fsck`/`resize2fs`/`mount` continuam funcionando
exatamente como hoje — sem lista `_SBIN_DIRS`, sem comportamento dependente de distro, sem
necessidade de remover os três `sudo` internos por correção. O Python do conda-forge é
relocável a partir de `sys.executable`, então nenhuma ativação é necessária; você já afirma isso
no doc ("O interpretador não depende de env nenhuma") sem perceber que dissolve o problema.

Note que a alternativa do briefing — `sudo $(command -v pixi) run ...` — *não* é a comparação
certa, e o plano já sabe por quê (root vira dono do `.pixi/`, aviso no README, linha 350).
A comparação viável é o caminho do interpretador puro acima.

**Veredito sobre a auto-elevação: não vale a pena, e o custo é maior do que o doc declara** — não
é uma flag, é `--no-elevate` + cirurgia de parser-pai em todos os subparsers + semântica de
`SUPPRESS` + override por variável de ambiente + sentinela + `_elevated_path()` + uma regressão de
segurança documentada, tudo para poupar cinco caracteres do usuário.

## 2. `pixi run install -a 11 gapps` está quebrado — e `-a` é a flag que mais importa

`-a/--android-version` está no parser **de topo** (`main.py:287-291`), adicionado depois dos
subparsers. Verificado:

```
['install','gapps']            -> OK
['install','-a','11','gapps']  -> SystemExit 2   ← o que as tasks do pixi produzem
['-a','11','install','gapps']  -> OK
```

É exatamente o modo de falha que o doc gasta uma seção inteira consertando para o `--no-elevate` —
e conserta *só* para o `--no-elevate`. Cada uma das quatro tasks propostas (`install`, `uninstall`,
`certified`, `hack`) trava o usuário em Android 13 sem outra saída além de contornar o pixi.

`android_version` comanda Gapps, Ndk, Houdini, Widevine, MicroG, FDroidPriv e Nodataperm
(`main.py:67-144`). Não é caso de canto. O `-a` precisa do mesmo tratamento com `parents=[...]`,
e a revisão passou por cima olhando diretamente para o padrão.

## 3. `lzip` — a única justificativa de pixi sobre uv — só é usado no caminho Android 11

O `grep` diz que `--lzip` aparece em `gapps.py:126,147`, ambos dentro de `copy_11()`. O `copy_13()`
(`gapps.py:157+`) percorre uma árvore `system/` já extraída via `zipfile` — **sem tar, sem lzip**.
O default do projeto é A13 (`db43c7c`).

Ou seja, a tese do "What Makes This Cool" vale apenas para um caminho de código que:
- não é o padrão,
- é inalcançável pelas tasks do próprio plano (achado 2),
- aponta para builds do OpenGApps no SourceForge de 2022, que a sua Premissa 6 e a issue #238
  do upstream sinalizam como apodrecidos.

Combinando 1+2+3: o plano constrói um caminho de escalada de privilégio e um esquema de
propagação de PATH para garantir a reprodutibilidade de um binário usado por um caminho de código
legado, inalcançável e provavelmente quebrado.

Isso não significa que pixi esteja errado — lockfile e Python pinado valem a pena, e `pixi install`
realmente ganha de três passos de README. Significa que **o argumento de pixi sobre PEP 723/uv
(#269), como está escrito, é bem mais fraco do que o doc afirma**, e o doc deveria dizer isso
honestamente em vez de liderar com o `lzip`. A vantagem real que resta sobre o uv: `pixi.lock`
existe e PEP 723 não tem lockfile. É só isso. Reescreva a seção "What Makes This Cool" de acordo,
ou alguém reabre isso em três meses com os mesmos dados que eu acabei de puxar.

(Nota lateral: a `#204` pede um *binário único executável* e a `#240` pede *empacotamento Python
adequado*. Nenhuma das duas é o que pixi + `git clone` entrega — o doc diz explicitamente
"sem PyPI, sem binário". Citá-las como validação de demanda é racionalização a posteriori.)

## 4. A decisão 3 está errada como composta — ela mantém metade do bug

`returncode not in ok_codes AND stderr não vazio` não é uma composição, são duas alternativas
fundidas. A allowlist de `ok_codes` **sozinha** resolve o caso do `mountpoint`:

Verificado: `mountpoint /caminho/que/nao/e/mount` → **rc=32, stderr vazio, mensagem em stdout**.
Então `run(["mountpoint", mp], ok_codes=(0,1,32))` devolve o resultado, `images.py:20` lê
`.returncode` sem mudar nada, pronto.

Manter o conjunto `stderr` não compra nada e custa isto: **qualquer comando que falhe com stderr
vazio é silenciosamente tratado como sucesso.** É o espelho exato do bug que você está
consertando. O `e2fsck` escreve a maior parte da saída em *stdout* — código 8 (erro operacional)
com mensagem só em stdout → `run()` devolve "sucesso" → `resize2fs` prossegue sobre um sistema de
arquivos que falhou na verificação. Você terá reintroduzido a classe da issue #202 no call site da
própria issue #202.

Descarte o conjunto. Levante em `returncode not in ok_codes`, ponto.

**E ninguém nomeou os `ok_codes` concretos.** O `e2fsck` sai com **1** quando corrigiu erros com
sucesso e **2** quando corrigiu e quer reboot. Os dois são sucesso. `images.py:27` precisa de
`ok_codes=(0,1,2)` ou a "correção" faz o `resize()` falhar no desfecho não-trivial mais comum de
um fsck. Isso é bloqueador das decisões 2 e 3.

## 5. `helper.shell()` tem o mesmo bug e nenhuma decisão cobre

`tools/helper.py:76-83`:

```python
if a.stderr.read():
    Logger.error(a.stderr.read().decode('utf-8'))   # ← segunda leitura devolve b''
    raise subprocess.CalledProcessError(
        returncode=a.returncode,                     # ← None; wait() nunca é chamado
```

Três bugs empilhados: a mesma condição de "stderr significa erro" do `run()`, a mensagem de erro
*sempre vazia* (o pipe foi drenado pelo `if`), e `returncode` é `None` porque nada chama `wait()` —
produzindo `returned non-zero exit status None`.

`shell()` é o motor do `android_id.py`, ou seja, do subcomando `certified` — uma das suas quatro
tasks do pixi, e assunto da issue #259 do upstream. A decisão 2 diz "consertar a causa raiz";
o PR #258 só toca em `run()`. Se a alegação principal do fork é "consertamos o bug do returncode",
entregar isso com o `shell()` intocado é alegação falsa. Inclua.

## 6. A checagem de prefixo do `check_system_deps()` é no-op fora do pixi — e é justamente o ponto da Approach B

```python
elif not path.startswith(sys.prefix):
```

Verificado: fora do pixi, `sys.prefix == "/usr"` e `shutil.which("tar") == "/usr/bin/tar"` →
`startswith` é **True** → a guarda passa. A checagem tem sucesso silencioso exatamente no cenário
que ela existe para detectar. O plano documenta `python main.py --no-elevate install gapps` como
uso suportado (linha 292), então esse caminho é alcançável por desenho.

Correção: afirme que um ambiente pixi/conda está ativo (`sys.prefix != sys.base_prefix`, ou
`CONDA_PREFIX`), ou compare `os.path.dirname(path) == os.path.join(sys.prefix, "bin")` *mais* a
checagem de prefixo. Ou — pelo achado 1 — apague a categoria inteira.

**Separadamente, a guarda é ampla demais.** Ela roda em `main.py:349/352` antes do dispatch, para
todo subcomando, e aborta duro em `mount`, `mountpoint`, `umount`, `e2fsck`, `resize2fs`, `lzip` e
`tar`. O `certified` precisa apenas de `waydroid`. O `install gapps` em A13 não precisa de `lzip`.
Você construiu um portão global para um programa onde cada subcomando usa um subconjunto
diferente. Torne-a por comando ou preguiçosa, ou você trocou uma falha real por uma espúria.

## 7. A justificativa declarada da decisão 6 é provavelmente falsa — `ubuntu-latest` não reproduz o bug de sbin

Os runners `ubuntu-*` do GitHub Actions definem o PATH do usuário do runner incluindo
`/usr/local/sbin:/usr/sbin:/sbin` (é montado pelo serviço do runner, não por um shell de login
Debian). **Verifique isso antes de construir o workflow** — um `echo $PATH | tr : '\n' | grep sbin`
num job descartável resolve. Se confirmar, a decisão 6 não compra nada do que alega comprar.

Dois outros problemas com ela, independentemente:
- O CI **não consegue** rodar `pixi run install gapps`. Precisa de root, privilégio de mount,
  `/var/lib/waydroid/waydroid.cfg` e um container Waydroid inicializado. Então o Critério 13
  continua manual, faça o workflow o que fizer.
- O comportamento de sbin é função pura do PATH. `_elevated_path()` e `check_system_deps()` são
  testáveis com um `PATH` monkeypatchado em *qualquer* máquina, em pytest, em milissegundos. Esse
  é o trabalho da decisão 7, não da decisão 6.

Mantenha o workflow (é barato e roda `pixi install` + pytest, o que vale ter), mas pare de alegar
que ele cobre a lacuna do Debian. Não cobre.

## 8. A decisão 4 dá chown na coisa errada

Duas lacunas:

**(a) Arquivos, não só o diretório.** O `get_download_dir()` cria o diretório; o `download_file()`
depois escreve `gapps.zip` (centenas de MB) dentro dele *como root*. Dar chown no diretório deixa
um arquivo com dono root dentro do `~/.cache` do usuário, que ele não consegue apagar e que trava
qualquer execução não-root posterior. Dê chown nos arquivos baixados também, ou `os.umask` +
chown depois de cada `download_file()`.

**(b) O caminho está errado em algumas distros.** `tools/helper.py:19,31` monta
`/home/<SUDO_USER>/...` por concatenação de string. No Fedora Silverblue / Universal Blue, os homes
ficam em `/var/home/<user>`. O `ublue-os/waydroid_script` é um dos cinco forks da sua própria
triagem. Use `pwd.getpwnam(user).pw_dir`. Mesmo bug no `get_data_dir()` — que o autor original já
marcou com `# not good`. Se você vai tocar nesse código para o chown de qualquer jeito, conserte
no mesmo commit.

Também: `os.environ["USER"]` levanta `KeyError` quando `USER` não está definido (containers, CI,
alguns contextos de systemd). Use `.get()` com fallback baseado em `pwd`.

## 9. A decisão 1 conflita com a decisão 2 e com a postura de fork (D4)

Você está propondo pousar o PR upstream de outro autor (#258, `i-am-very-smart`, aberto há 8 meses)
como uma linha anônima dentro de uma migração de toolchain grande e única. Isso:
- apaga a autoria,
- torna a mudança impossível de cherry-pickar pelo upstream ou pelos outros 281 forks,
- contradiz a postura "sucessor de fato, remote `upstream` mantido" da D4, que só significa alguma
  coisa se você tornar seu trabalho *pegável*.

Pouse o #258 como commit próprio creditando o autor original (idealmente um merge real do PR),
antes ou separado da migração. A sua própria triagem chega à mesma conclusão (seção 6) e o plano
ignorou.

Mais amplamente: a decisão 1 agora empacota a reescrita do `run()` + a reescrita do `shell()` +
auto-elevação + cirurgia de parser + remoção de `sudo` em três lugares + afrouxamento de regex +
uma suíte pytest do zero + um workflow de CI + uma reescrita de README + remoção do Nix. Contra
um repositório de 3740 estrelas, vindo de um mantenedor novo, sem cobertura de teste prévia. Isso
não é revisável, inclusive por você daqui a seis meses quando estiver bissectando.

## 10. Estratégico: este é o primeiro ato errado para o fork

A sua triagem tem a resposta e o plano não a absorveu. Seis PRs estão abertos, limpos e de graça:
#258 (4 issues), #284, #274, #270, #266, #218. Um commit de fork (`WayDroid-ATV:a14`, GApps para
A13TV/14/15) aplica limpo. A issue #282 se chama literalmente *"It seems Project is abandoned"*
(2026-08).

O sinal de que um fork assumiu é um release que conserta coisas de que os usuários estão
reclamando. A migração pixi conserta zero issues reportadas, e *sobe* a barreira de entrada para
todo usuário existente que já tem um venv funcionando (ferramenta nova obrigatória, distribuição
só por `git clone`, sem PyPI, sem AUR).

A justificativa declarada do sequenciamento — "comparar código contra uma base que ainda vai mudar
gera trabalho jogado fora" — não sobrevive ao contato com os diffs reais. O #258 é +1/−1 no
`run()`. O #270 são vírgulas faltando em `microg.py`. O #266 é uma linha de README. Nenhum deles
toca em `check_root()`, `check_system_deps()`, `pixi.toml` ou na fiação do argparse. Não há
conflito a evitar. O argumento do sequenciamento protege contra um custo que não existe aqui.

Faça as correções baratas primeiro, marque um release, *depois* migre o toolchain. Você também
terá usuários reais testando em Debian, que é a única coisa de que o Critério 13 precisa e o CI
não consegue dar.

## 11. Menores

- **Decisão 5** — o `requires-pixi` só é interpretado por um pixi novo o bastante para conhecer a
  chave; um pixi mais velho dá erro de campo desconhecido, que é justamente a mensagem confusa que
  o doc diz estar prevenindo. E fixar `>=0.55` (sua versão testada) exclui 0.39–0.54 sem razão
  demonstrada, contradizendo o piso de 0.39 do próprio doc. Escolha um e declare qual falha você
  está de fato prevenindo.
- **O Critério 2 promete demais.** A reprodutibilidade cobre 3 pacotes Python + `lzip` + `tar`. O
  comportamento do programa continua dependendo de `mount`/`e2fsck`/`waydroid` do host e de 30 URLs
  remotas fixas cujo conteúdo já está derivando (#238). Diga isso na descrição do PR ou soa como
  alegação maior do que é.
- **Escopo da decisão 7.** A base de código é largamente não testável como está — `run()`/`shell()`
  batem em subprocess diretamente, `extract_to = "/tmp/gapps/extract"` é atributo de classe,
  `General.install()` muta `/var/lib/waydroid`. Primeira suíte realista: `helper.host()`, a lógica
  de `ok_codes` do `run()` (monkeypatch em `subprocess.run`), `_elevated_path()`/tratamento de PATH,
  e a fiação do argparse (incluindo o `-a`, pelo achado 2). Escreva esse escopo ou "adicionar
  pytest" vira ilimitado.
- **A linha 1 do `.gitignore` é a string literal `git`.** Correção de graça enquanto adiciona
  `.pixi/`.
- **Disponibilidade no conda-forge confirmada** (consultei a API): `tar` 1.35, `lzip` 1.21,
  `inquirerpy` 0.3.4 (noarch), todos presentes para `linux-64` + `linux-aarch64`. O `e2fsprogs`
  mais recente no conda-forge é de fato **1.46.2** — a inclinação "host" da OQ-E2FSPROGS está
  correta; feche a questão.
- **A dúvida sobre `dbus-python`/`gbinder`/`PyGObject` do PR #269 está respondida**: a única
  referência no repositório é um `# import dbus` comentado em `tools/container.py:4`. O autor do PR
  copiou a lista de dependências do próprio Waydroid. Não falta nada no `requirements.txt`.
  Encerre essa linha.
- **A OQ-PLATAFORMAS está superdimensionada.** Um *host* x86 de 32 bits ou ARMv7 rodando Waydroid
  em 2026 é essencialmente hipotético. Aceite, documente em uma linha, feche.

---

## O que eu verifiquei depois, na máquina

| Achado | Verificado? | Resultado |
|---|---|---|
| 2 — `-a` depois dos subparsers | **Sim** | `['install','-a','11','gapps']` → `SystemExit 2`. Confirmado |
| 3 — `lzip` só em `copy_11` | **Sim** | `--lzip` em 126 e 147, ambos entre `copy_11` (113) e `copy_13` (157) |
| 4 — `mountpoint` rc=32, stderr vazio | **Sim** | `returncode=32`, mensagem em stdout, stderr vazio |
| 5 — `shell()` lê stderr duas vezes, returncode None | **Sim** | Confirmado em `helper.py:83-87` |
| 6 — prefixo é no-op fora do pixi | **Sim** | `sys.prefix` = `/usr`, `which("tar")` = `/usr/bin/tar` → `startswith` True |
| 11 — `.gitignore` linha 1 é `git` | **Sim** | Confirmado |
| 11 — deps do PR #269 | **Sim** | Só `# import dbus` comentado em `container.py:4` |
| **1 — caminho absoluto dissolve o PATH** | **Sim, com correção** | Ver abaixo |
| 7 — `ubuntu-latest` tem sbin no PATH | **Não** | Exige rodar um job no GitHub. Fica em aberto |
| 8b — `/var/home` no Silverblue | **Não** | Não tenho Silverblue aqui. Plausível e barato de blindar com `pwd` |

### A correção ao achado 1

O agente disse que basta chamar o `tar` por caminho absoluto. **Isso não funciona**: o próprio
GNU tar procura o `lzip` no PATH quando recebe `--lzip`. Testado nesta máquina, que não tem `lzip`
instalado no host:

```
A) /usr/bin/tar --lzip -xf t.tar.lz            (PATH=/usr/bin:/bin)
   → tar (child): lzip: Cannot exec: No such file or directory
   → FALHOU

B) /usr/bin/tar --use-compress-program=<abs>/lzip -xf t.tar.lz   (mesmo PATH pelado)
   → extraiu
```

A conclusão do agente sobrevive, o mecanismo muda: é preciso `--use-compress-program` apontando
para o `lzip` do env por caminho absoluto. Com isso, a propagação de PATH realmente se torna
desnecessária, e a garantia fica mais forte do que o desenho original.
