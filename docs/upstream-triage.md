# Triagem do upstream: forks e issues

Levantado em 2026-09-02 contra `casualsnek/waydroid_script` via API do GitHub.
Estado do upstream: **3740 estrelas, 281 forks, 124 issues abertas, 28 PRs abertos, último push em 2026-01-05.**

---

## 1. Os cinco forks mais populares

| # | Fork | ★ | Último push | vs upstream | Veredito |
|---|---|---|---|---|---|
| 1 | `ayasa520/waydroid_script` | 57 | 2026-01-04 | `rikka_main`: +48 / −109 | **Dormente.** Os 48 commits são todos de 2023 e a maioria já foi absorvida pelo upstream (CLI interativa, MinMicroG, o próprio venv). Nenhuma das 8 branches tem trabalho posterior a 2023-08 |
| 2 | `ublue-os/waydroid_script` | 10 | 2025-08-03 | +9 / −5 | **Semi-ativo.** Fork do time Universal Blue. 6 dos 9 commits são merges. Conteúdo próprio: fix do microG Minimal/MinimalIAP e correção de permissões + MD5 do smartdock |
| 3 | `worstperson/waydroid_script` | 8 | 2024-12-30 | +2 / −12 | **Parado.** Dois commits, mensagens "hacks" e "fix" |
| 4 | `HuskyDG/waydroid_script` | 6 | 2022-10-24 | — | **Deletado.** API devolve 404; as estrelas são dado morto no índice de forks |
| 5 | `WayDroid-ATV/waydroid_script` | 6 | **2026-02-23** | branch `a14`: +1 / −0 | **O único com coisa nova.** Um commit, em dia com o upstream: *"Add GApps for A13TV/14/15"* |

### Conclusão

**Não existe fork sucessor ativo.** Nenhum dos 281 forks assumiu a manutenção. O mais recente empurrou um commit em fevereiro e parou; o mais popular está dormente desde 2023.

Isso fecha a OQ-FORK do design doc de migração e valida a postura de sucessor de fato: o campo está aberto.

### O único commit que vale trazer

`WayDroid-ATV:a14` → **"Add GApps for A13TV/14/15"** (2026-02-23). O upstream só tem MindTheGapps 13.0.0 em `stuff/gapps.py`. Este commit está `ahead=1, behind=0`, ou seja, aplica limpo sobre o `main` atual.

---

## 2. As 124 issues abertas, por subsistema

| Subsistema | Issues | De 2025+ | Mais recente |
|---|---|---|---|
| Tradução ARM (houdini/libndk) | 24 | 6 | #268 Libhoudini do ChromeOS Brya v145 (2026-03) |
| Magisk / Zygisk | 17 | 2 | #283 `/data/adb/magisk` sem permissão de execução (2026-08) |
| GApps | 10 | 3 | #254 falha ao instalar gapps (2025-12) |
| Certificação Play / android_id | 7 | 3 | #259 (2026-01) |
| Setup / Python / venv | 6 | 2 | #251 (2025-11) |
| Mount / imagem / resize | 6 | 1 | #216 suporte a imagem x86 (2025-03) |
| SmartDock | 5 | 0 | #207, #201, #163 — **todas sobre URL expirada** |
| microG | 4 | 2 | #273 IndexError em algumas variantes (2026-06) |
| Runtime do Waydroid | 3 | 2 | #277 (2026-07) |
| nodataperm / hacks | 2 | 2 | #264 crash no A13 (2026-02) |
| Widevine | 2 | 1 | #244 sem suporte no A13 arm64 (2025-09) |
| mitm / certificado | 1 | 0 | #120 (2023-09) |
| Outros | 36 | 13 | #282 *"It seems Project is abandoned"* (2026-08) |

Labels são inúteis: 124 issues, 5 rotuladas ao todo.

---

## 3. O achado principal: um bug explica quatro issues

**`tools/helper.py:43`**

```python
if result.stderr:                    # ← condição errada
    error = result.stderr.decode("utf-8")
    if ignore and re.match(ignore, error):
        return result
    Logger.error(error)
    raise subprocess.CalledProcessError(
        returncode=result.returncode,   # ← vale 0 aqui
        cmd=result.args, stderr=result.stderr)
```

`run()` decide que houve erro olhando **se o comando escreveu qualquer coisa em stderr**, não o código de saída. Qualquer binário que emita aviso, banner de versão ou progresso em stderr — e sair com sucesso — derruba o script. E como o `returncode` repassado é 0, a exceção produz a mensagem absurda que aparece nas issues:

> `Command '[...]' returned non-zero exit status 0.`

**Issues abertas causadas por isso:**

- **#202** (2024-12) — `e2fsck error - returned non-zero exit status 0`
- **#251** (2025-11) — `Python error. Command returned non-zero exit status 0.`
- **#271** (2026-05) — `Magisk install error` (mesma mensagem no corpo)
- **#277** (2026-07) — `Command '['waydroid', 'container', 'stop']' returned non-zero exit status 0.`

Os `ignore=` espalhados pelo código (`images.py:27-28`) são curativo sobre a condição errada: cada um é uma regex para calar um comando específico que ousou escrever em stderr ao ter sucesso. É exatamente o padrão de consertar o sintoma em cada chamador em vez da guarda na função compartilhada.

**Já existe PR aberto que conserta, uma linha:**

> **PR #258** — `tools/helper.py: run() only detects error if return code is non-zero`
> Autor: `i-am-very-smart` · aberto em 2026-01-11 · `mergeable_state: clean` · +1/−1
> ```diff
> -    if result.stderr:
> +    if result.returncode != 0 and result.stderr:
> ```

Aberto há oito meses. Uma linha, quatro issues.

Nota de interação com o design doc de migração: se este PR entrar, a OQ-E2FSPROGS muda de peso. As regexes de `ignore` em `images.py:27-28` deixam de ser o único anteparo — mas ainda vale afrouxá-las, porque `e2fsck` pode sair com código não-zero legítimo e a regex atual quebra em versão `1.47.10`.

---

## 4. PRs abertos que valem merge

Correções prontas, sem custo de escrita:

| PR | Data | O que faz | Fecha |
|---|---|---|---|
| **#258** | 2026-01 | `run()` só acusa erro com returncode ≠ 0 | #202, #251, #271, #277 |
| **#284** | 2026-08 | Permissões de `/data/adb/magisk` para o Zygisk inicializar | #283 |
| **#274** | 2026-06 | Corrige download das variantes Minimal e MinimalIAP do microG | #273 |
| **#270** | 2026-04 | Vírgulas faltando em `microg.py` | provável causa do IndexError de #273 |
| **#281** | 2026-08 | `tflitefix`: evita SIGSEGV em jogos que usam TensorFlow Lite | — |
| **#275** | 2026-06 | Device spoof para compatibilidade na Play Store | relacionado a #259, #248 |
| **#266** | 2026-03 | Renomeia o comando `google` para `certified` no README | corrige `README.md:68` |
| **#218** / **#185** | 2025-03 / 2024-08 | Atualiza URL do SmartDock | #207, #201, #163 |

**#266 é o mesmo bug** que a triagem do design doc tinha achado de forma independente em `README.md:68` (documenta `main.py google`, subcomando que não existe). Já tem PR.

---

## 5. O que isso diz sobre a migração para pixi

### Valida

Duas issues abertas pedem exatamente o trabalho já desenhado:

- **#240** (2025-07) — *"Needs proper Python packaging"*
- **#204** (2024-12) — *"Package the Python scripts into a single executable binary for easy distribution"*

Não é preferência pessoal de toolchain. É demanda registrada, em aberto, sem resposta.

### Concorre

**PR #269** (2026-04, `Alistair1231`) — *"add inline dependencies"*. Adiciona metadata PEP 723 no topo do `main.py` para rodar `sudo uv run main.py`, com o uv montando o venv sozinho.

É uma proposta séria e mais barata que a migração para pixi: dez linhas, um arquivo, nenhum lockfile, nenhuma ferramenta nova para quem já tem uv.

**Por que ela não substitui o pixi neste projeto:**

1. **Não resolve o `lzip`.** PEP 723 declara dependências *Python*. A dependência de sistema continua sendo problema do usuário, e a seção `pacman`/`apt`/`dnf`/`zypper` do README permanece.
2. **Tem o mesmo problema de `sudo` descrito no design doc.** `sudo uv run main.py` atravessa a mesma fronteira, com o mesmo descarte de PATH.
3. **Não fixa versão.** Sem lockfile, dois usuários no mesmo commit podem resolver árvores diferentes.

Detalhe que merece verificação antes de qualquer coisa: o PR declara `dbus-python`, `gbinder` e `PyGObject`, que **não** estão no `requirements.txt` atual. Ou o autor copiou a lista do próprio Waydroid, ou existe dependência não declarada no `requirements.txt` de hoje. Vale conferir antes de fechar o `pixi.toml`.

### Confirma a Premissa 6 (apodrecimento de URL)

A premissa dizia que as 30 URLs hardcoded são risco maior que toolchain. As issues concordam:

- **#257** (2026-01) — *"The provided libhoudini.so arm translator is no longer working in 2026"*
- **#268** (2026-03) — Libhoudini do ChromeOS Brya v145
- **#238** (2025-07) — *"md5 mismatches when downloading gapps.zip"* (URL mudou, md5 fixo não bate)
- **#207 / #201 / #163** — URL do SmartDock expirada, três vezes
- **#237** (2025-07, 15 comentários) — Waydroid não boota depois de instalar libhoudini no A13

Tradução ARM é o subsistema com mais issues abertas (24) e o segundo em atividade recente. É o próximo ciclo com nome e número.

---

## 6. Ordem sugerida

A ordem definida foi: pixi → forks → issues. Este documento é a etapa 2 antecipada, a pedido.

Uma tensão que vale decidir conscientemente: **PR #258 é uma linha e fecha quatro issues.** Segurá-lo até a migração pixi terminar é defensável (base estável primeiro), mas é o item de maior retorno por esforço de todo o levantamento.

Sugestão, se a ordem puder flexionar num ponto só: mergear #258 antes, porque ele não toca em nada que a migração pixi vai mexer — `check_root()` e `check_system_deps()` ficam noutra parte de `helper.py`, sem conflito.
