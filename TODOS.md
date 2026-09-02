# TODOS

## Downloads

### Laço de redownload sem teto quando o md5 não bate

**What:** Adicionar limite de tentativas ao laço de `stuff/general.py:42-46`, e transformar
o esgotamento das tentativas em erro legível.

**Why:** Quando a URL passa a servir um arquivo diferente do que o md5 fixo no código espera,
o md5 nunca bate. O laço apaga o arquivo, baixa de novo, confere, e repete sem teto. O usuário
vê `md5 mismatches, redownloading now ....` para sempre e queima a banda dele. É a issue
[#238](https://github.com/casualsnek/waydroid_script/issues/238) do upstream,
*"md5 mismatches when downloading gapps.zip"*.

**Context:** O código atual é:

```python
while not os.path.isfile(self.download_loc) or loc_md5 != self.act_md5:
    if os.path.isfile(self.download_loc):
        os.remove(self.download_loc)
        Logger.warning("md5 mismatches, redownloading now ....")
    loc_md5 = download_file(self.dl_link, self.download_loc)
```

O `act_md5` vem de tabelas fixas em `stuff/gapps.py:26,101` e `stuff/fdroidpriv.py:15,32`.
Onde começar: três tentativas e depois `Logger.error` nomeando a URL, o md5 esperado e o
recebido — assim o relato de bug já chega com o dado necessário para atualizar a tabela.

Isso é sintoma do problema maior registrado como Premissa 6 no design doc da migração pixi:
30 URLs hardcoded, várias já podres (`#257` libhoudini, `#238` gapps, `#207/#201/#163`
smartdock). O apodrecimento de URL neste código não dá erro, dá laço infinito. Vale atacar
os dois juntos: teto de tentativas + auditoria das URLs.

**Effort:** S
**Priority:** P1
**Depends on:** None. Independente da migração pixi.

### md5 carrega o arquivo inteiro na memória, duas vezes

**What:** Trocar `hashlib.md5(f.read())` por leitura em blocos, e deduplicar as duas cópias
do mesmo cálculo em `tools/helper.py:103-104` e `stuff/general.py:39-41`.

**Why:** O pico de memória é o tamanho do arquivo baixado, e acontece duas vezes — uma ao
baixar, outra ao validar o cache existente. Zips de gapps têm centenas de MB, e Waydroid roda
muito em máquina modesta e em SBC ARM.

**Context:** O `download_file` já baixa em blocos de 1 KiB com barra de progresso
(`tools/helper.py:94-102`); só o cálculo do md5 logo depois é que engole o arquivo inteiro de
uma vez. A correção é mecânica: `while chunk := f.read(65536)`. As duas ocorrências fazem
exatamente a mesma coisa e deveriam virar uma função só em `tools/helper.py` — há duplicação
real ali, não coincidência.

**Effort:** S
**Priority:** P2
**Depends on:** None. Casa bem com o item acima, no mesmo ciclo de sanidade de download.
