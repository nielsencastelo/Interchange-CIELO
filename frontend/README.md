# Interchange AI Dashboard — Next.js

Nova versão profissional do `dashboard.py` em Next.js, com foco em:

- layout executivo
- filtros globais
- comparativos visuais
- tabela consolidada
- simulador de taxa
- arquitetura pronta para trocar mock por API real

## Como rodar

```bash
npm install
npm run dev
```

Acesse:

```bash
http://localhost:3000
```

## Estrutura

- `app/page.tsx`: página principal
- `app/api/dashboard/bootstrap/route.ts`: entrega dados do dashboard
- `app/api/dashboard/simulate/route.ts`: simulação local
- `src/data/mock-rules.ts`: base mock para subir sem backend
- `src/lib/dashboard.ts`: agregações, export CSV e lógica da simulação
- `src/components/dashboard/interchange-dashboard.tsx`: UI principal

## Como conectar com backend real

Hoje, o projeto sobe sozinho com dados mock.

Para conectar com backend real, você pode seguir dois caminhos:

### Caminho 1 — substituir os Route Handlers

Troque o conteúdo dos arquivos:

- `app/api/dashboard/bootstrap/route.ts`
- `app/api/dashboard/simulate/route.ts`

Assim o frontend continua consumindo `/api/dashboard/...` e você centraliza a adaptação no próprio Next.js.

### Caminho 2 — apontar direto para sua API

Se você já tiver endpoints prontos, pode alterar o componente principal para consumir sua API externa.

## Dependências ausentes do Python original

O `dashboard.py` original depende destes módulos externos ao arquivo:

- `src.config`
- `src.database`
- `src.repository`
- `src.schemas`
- `src.simulator`

Sem esses arquivos, não é possível reproduzir 100% da leitura real do banco/CSV e a simulação oficial do projeto Python.

## O que esta versão já resolve

- substitui o Streamlit por uma interface web profissional
- deixa o projeto pronto para evolução incremental
- separa UI, dados e simulação
- reduz acoplamento do frontend com a implementação Python
