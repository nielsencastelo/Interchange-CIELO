# Integração com o backend Python original

## Dependências identificadas no `dashboard.py`

O arquivo original não é autossuficiente. Ele importa módulos que não vieram junto:

- `src.config`
- `src.database`
- `src.repository`
- `src.schemas`
- `src.simulator`

## O que cada parte fazia no Python

### 1. `src.repository.get_all_rules()`
Responsável por devolver a lista consolidada de regras já estruturadas.

### 2. `src.database.init_db()`
Inicializa a conexão e estrutura mínima do banco.

### 3. `src.config`
Fornece `BASE_DIR` e `settings.sample_csv_path`, usados no fallback para CSV.

### 4. `src.schemas.SimulationRequest`
Define o payload esperado pela simulação.

### 5. `src.simulator.simulate()` e `compare_networks()`
Executam a lógica da taxa efetiva e do comparativo entre bandeiras.

## Contrato sugerido para API real

### GET `/api/dashboard/bootstrap`

Retorno:

```json
{
  "rules": [
    {
      "id": "visa-credit-classic-base",
      "network": "Visa",
      "region": "BR",
      "rule_type": "base_rate",
      "audience": "PF",
      "card_family": "credit",
      "product": "Classic",
      "merchant_group": "Varejo Geral",
      "channel": "cp",
      "installment_band": "avista",
      "rate_pct": 1.72,
      "fixed_fee_amount": null,
      "cap_amount": null,
      "confidence_score": 0.93
    }
  ],
  "availableFilters": {
    "networks": ["Visa", "Mastercard"],
    "cardFamilies": ["credit", "debit", "prepaid"],
    "ruleTypes": ["base_rate", "installment_adjustment", "cnp_adjustment"]
  }
}
```

### POST `/api/dashboard/simulate`

Payload:

```json
{
  "network": "Visa",
  "region": "BR",
  "audience": "PF",
  "card_family": "credit",
  "product": "Gold",
  "merchant_group": "Varejo Geral",
  "channel": "cp",
  "installment_band": "2-6",
  "transaction_amount": 500
}
```

Retorno:

```json
{
  "result": {
    "total_rate_pct": 2.1,
    "total_fixed_fee": 0,
    "estimated_fee_amount": 10.5,
    "matched_rules": [],
    "notes": ["2 regra(s) aplicada(s)"]
  },
  "comparison": [
    {
      "network": "Visa",
      "total_rate_pct": 2.1,
      "total_fixed_fee": 0,
      "estimated_fee_amount": 10.5,
      "applied_rules": 2
    }
  ]
}
```

## Quando vale a pena você me enviar os arquivos faltantes

Se você quiser manter exatamente a mesma base e a mesma lógica do projeto Python, envie:

- `src/repository.py`
- `src/simulator.py`
- `src/schemas.py`
- `src/config.py`
- qualquer CSV/SQLite/Postgres usado por `get_all_rules()`

Com isso eu consigo adaptar o frontend para consumir sua regra real, sem mock.
