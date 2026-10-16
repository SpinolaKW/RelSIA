# RelSIA — interface renovada

Esta versão adapta o Sistema SIA 2.21 ao estilo da referência enviada: navegação lateral escura, área de trabalho clara, verde discreto, cartões de indicadores e filtros recolhíveis. Continua usando Python e CustomTkinter.

## Abrir no Windows

1. Extraia o ZIP inteiro em uma pasta nova.
2. Com Python 3.11 ou superior instalado, execute `install.bat`.
3. Execute `run.bat`.
4. No primeiro acesso, cadastre a senha do administrador. Não há senha predefinida.

Não é necessário criar uma pasta `assets`. Os ícones da interface são desenhados localmente por `src/sia_app/ui/icons.py`. O tema está em `src/sia_app/ui/relsia_theme.json` e sua paleta compartilhada em `theme.py`.

O logotipo usado nos PDFs é uma configuração separada: ele pode ser escolhido na tela de configurações. Na primeira abertura, o sistema pode solicitar a configuração dos relatórios.

## O que mudou

- Janela principal com menu lateral e indicação da seção atual.
- Menu compacto automático em janelas menores.
- Login com a identidade RelSIA e os mesmos controles de acesso.
- Dashboard com seis indicadores, carregamento inicial automático e filtros que podem ser exibidos ou recolhidos.
- Cores e fontes compartilhadas nas telas existentes.
- Ícones gráficos que não dependem de caracteres especiais ou downloads.
- Cancelamento de desenhos pendentes ao encerrar o dashboard.
- Correção da recriação da janela no teste gráfico, evitando referências a frames já destruídos.

### Refinamentos desta revisão

- Menu organizado em Análise, Gestão e Administração, com descrições para os ícones.
- Busca de telas por `Ctrl+K`; use as setas para selecionar, Enter para abrir e Esc para fechar. A pesquisa aceita nomes sem acentos e lista apenas as telas permitidas para o perfil conectado.
- `Ctrl+R` atualiza o dashboard quando ele está aberto. `Ctrl+1` até `Ctrl+8` abrem as opções disponíveis, na ordem do menu.
- Panorama com a quantidade produzida, a quantidade aprovada, a aprovação percentual e a diferença entre as duas quantidades.
- Cartões financeiros mais legíveis, resumo completo dos filtros e orientação para consultas sem produção.
- Cabeçalhos compartilhados, tabelas com seleção legível e rolagem com cores consistentes.

A aprovação por quantidade é calculada como quantidade aprovada dividida pela quantidade produzida, multiplicada por 100. Sem quantidade produzida, o percentual aparece como “—”. A diferença apresentada é quantidade produzida menos quantidade aprovada. Os indicadores respeitam os filtros aplicados.

Os serviços de importação, cálculos, geração de PDF/CSV, autenticação e estrutura do banco foram mantidos. O pacote não contém banco real nem credenciais.

## Dados existentes

Em código-fonte, o padrão é a pasta `data` ao lado de `run.py`. No executável Windows, o código existente usa `%LOCALAPPDATA%\Sistema_SIA\data`. A variável `SIA_DATA_DIR` permite escolher outra pasta.

Para avaliar esta versão com dados existentes, faça primeiro uma cópia consistente pelo backup do sistema e trabalhe com essa cópia. A atualização não inclui migração dos seus arquivos reais. Não copie apenas o arquivo `.db` enquanto outra instância estiver gravando: o banco usa SQLite WAL.

O arquivo `Abrir_SIA_REDE_MODELO.bat` foi preservado como modelo de distribuição do aplicativo. Ele não implementa um banco central compartilhado. O SQLite em modo WAL não deve ser acessado diretamente por vários computadores através de uma pasta de rede; essa implantação exige uma solução separada.

## Validar e gerar o executável

- Execute `validate_windows.bat` para os testes do núcleo, do banco e das telas.
- Execute `GERAR_EXECUTAVEL.bat` para compilar no próprio Windows.
- O resultado é `dist\RelatorioSIA\RelatorioSIA.exe`. Distribua a pasta `RelatorioSIA` inteira, incluindo `_internal`.
- O banco real não é incorporado à compilação. A primeira execução cria um banco vazio se não houver um banco existente na pasta de dados configurada.

O código foi validado em Linux com Python 3.12, dependências nas versões declaradas e servidor gráfico de testes. Passaram 36 testes (29 originais e 7 de interface), o autoteste SQLite e a navegação nas oito telas do Administrador e nas três do Visualizador. O executável Windows ainda precisa ser compilado e conferido no Windows.

As capturas na pasta `docs` foram feitas da aplicação em execução com dados fictícios. Elas não representam uma base real. A renderização das fontes pode variar conforme o Windows e sua escala de exibição.

## Desenvolvimento em Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python run.py --self-test
.venv/bin/python run.py
```

Os testes de interface exigem uma sessão gráfica (`DISPLAY` no Linux). Sem ela, os sete testes de interface são marcados como ignorados; isso não valida as telas. O comando `run.py --ui-smoke-test` percorre os dois perfis em um banco de testes quando `SIA_DATA_DIR` aponta para uma pasta temporária.
