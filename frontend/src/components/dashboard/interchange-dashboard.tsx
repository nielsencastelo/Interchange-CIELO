'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  BarChart3,
  CreditCard,
  Download,
  Filter,
  LoaderCircle,
  Percent,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

import { toCsv } from '@/src/lib/dashboard';
import {
  CompareNetworkResult,
  DashboardBootstrap,
  InterchangeRule,
  SimulationInput,
  SimulationResult,
} from '@/src/types/interchange';

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2, minimumFractionDigits: 2 });

const chartColors = ['#5B7CFA', '#00B8A9', '#FF8A65', '#9C6ADE', '#FFD166', '#5CC8FF'];

type TabKey = 'rules' | 'visuals' | 'products' | 'simulator' | 'regulatory';

const tabOptions: Array<{ key: TabKey; label: string }> = [
  { key: 'rules', label: 'Tabela de Regras' },
  { key: 'visuals', label: 'Comparativos Visuais' },
  { key: 'products', label: 'Análise por Produto' },
  { key: 'simulator', label: 'Simulador' },
  { key: 'regulatory', label: 'Regulatório' },
];

export function InterchangeDashboard() {
  const [bootstrap, setBootstrap] = useState<DashboardBootstrap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('rules');

  const [selectedNetworks, setSelectedNetworks] = useState<string[]>([]);
  const [selectedCardFamilies, setSelectedCardFamilies] = useState<string[]>([]);
  const [selectedRuleTypes, setSelectedRuleTypes] = useState<string[]>([]);
  const [minConfidence, setMinConfidence] = useState(0);

  const [simulationInput, setSimulationInput] = useState<SimulationInput>({
    network: 'Visa',
    region: 'BR',
    audience: 'PF',
    card_family: 'credit',
    product: 'Gold',
    merchant_group: 'Varejo Geral',
    channel: 'cp',
    installment_band: null,
    transaction_amount: 500,
  });
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [comparison, setComparison] = useState<CompareNetworkResult[]>([]);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    async function bootstrapDashboard() {
      try {
        setLoading(true);
        const response = await fetch('/api/dashboard/bootstrap', { cache: 'no-store' });
        if (!response.ok) throw new Error('Falha ao carregar os dados do dashboard.');
        const data = (await response.json()) as DashboardBootstrap;
        setBootstrap(data);
        setSelectedNetworks(data.availableFilters.networks);
        setSelectedCardFamilies(data.availableFilters.cardFamilies);
        setSelectedRuleTypes(data.availableFilters.ruleTypes);
        setSimulationInput((current) => ({
          ...current,
          network: data.availableFilters.networks[0] ?? current.network,
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro inesperado ao carregar os dados.');
      } finally {
        setLoading(false);
      }
    }

    bootstrapDashboard();
  }, []);

  const rules = bootstrap?.rules ?? [];

  const filteredRules = useMemo(() => {
    return rules.filter((rule) => {
      return (
        selectedNetworks.includes(rule.network) &&
        selectedCardFamilies.includes(rule.card_family) &&
        selectedRuleTypes.includes(rule.rule_type) &&
        rule.confidence_score >= minConfidence
      );
    });
  }, [rules, selectedNetworks, selectedCardFamilies, selectedRuleTypes, minConfidence]);

  const averageRate = useMemo(() => {
    const valid = rules.filter((rule) => rule.rate_pct !== null);
    if (!valid.length) return 0;
    return valid.reduce((acc, rule) => acc + (rule.rate_pct ?? 0), 0) / valid.length;
  }, [rules]);

  const averageByNetwork = useMemo(() => {
    const grouped = new Map<string, { total: number; count: number }>();
    filteredRules
      .filter((rule) => rule.rule_type === 'base_rate' && rule.rate_pct !== null)
      .forEach((rule) => {
        const current = grouped.get(rule.network) ?? { total: 0, count: 0 };
        grouped.set(rule.network, { total: current.total + (rule.rate_pct ?? 0), count: current.count + 1 });
      });

    return [...grouped.entries()].map(([network, value]) => ({
      network,
      rate_pct: Number((value.total / value.count).toFixed(2)),
    }));
  }, [filteredRules]);

  const distributionByRuleType = useMemo(() => {
    const grouped = new Map<string, number>();
    filteredRules.forEach((rule) => grouped.set(rule.rule_type, (grouped.get(rule.rule_type) ?? 0) + 1));
    return [...grouped.entries()].map(([name, value]) => ({ name, value }));
  }, [filteredRules]);

  const heatmapData = useMemo(() => {
    const grouped = new Map<string, { total: number; count: number }>();
    filteredRules
      .filter((rule) => rule.rate_pct !== null)
      .forEach((rule) => {
        const key = `${rule.network}__${rule.card_family}`;
        const current = grouped.get(key) ?? { total: 0, count: 0 };
        grouped.set(key, { total: current.total + (rule.rate_pct ?? 0), count: current.count + 1 });
      });

    return [...grouped.entries()].map(([key, value]) => {
      const [network, card_family] = key.split('__');
      return {
        network,
        card_family,
        rate_pct: Number((value.total / value.count).toFixed(2)),
      };
    });
  }, [filteredRules]);

  const productComparison = useMemo(() => {
    const grouped = new Map<string, { Visa?: number; Mastercard?: number }>();
    filteredRules
      .filter(
        (rule) =>
          rule.rule_type === 'base_rate' &&
          rule.rate_pct !== null &&
          rule.card_family === 'credit' &&
          (rule.audience === 'PF' || rule.audience === 'ALL') &&
          ['Visa', 'Mastercard'].includes(rule.network),
      )
      .forEach((rule) => {
        const current = grouped.get(rule.product) ?? {};
        grouped.set(rule.product, { ...current, [rule.network]: Number(rule.rate_pct?.toFixed(2)) });
      });

    return [...grouped.entries()].map(([product, values]) => ({ product, ...values }));
  }, [filteredRules]);

  const installmentAdjustments = useMemo(() => {
    return filteredRules
      .filter((rule) => rule.rule_type === 'installment_adjustment' && rule.rate_pct !== null)
      .map((rule) => ({
        installment_band: rule.installment_band,
        network: rule.network,
        rate_pct: Number(rule.rate_pct?.toFixed(2)),
      }));
  }, [filteredRules]);

  const debitReference = useMemo(() => {
    return rules
      .filter((rule) => rule.card_family === 'debit' && rule.rule_type === 'base_rate' && rule.rate_pct !== null)
      .map((rule) => ({ network: rule.network, rate_pct: Number(rule.rate_pct?.toFixed(2)), merchant_group: rule.merchant_group }));
  }, [rules]);

  function toggleFilter(list: string[], setter: (values: string[]) => void, value: string) {
    if (list.includes(value)) {
      setter(list.filter((item) => item !== value));
      return;
    }
    setter([...list, value]);
  }

  function downloadFilteredCsv() {
    const csv = toCsv(filteredRules);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'interchange_rules_filtered.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  async function runSimulation() {
    try {
      setSimulating(true);
      const response = await fetch('/api/dashboard/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(simulationInput),
      });

      if (!response.ok) throw new Error('Falha ao executar a simulação.');
      const data = (await response.json()) as { result: SimulationResult; comparison: CompareNetworkResult[] };
      setSimulationResult(data.result);
      setComparison(data.comparison);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro inesperado ao simular.');
    } finally {
      setSimulating(false);
    }
  }

  if (loading) {
    return (
      <main className="page-shell centered-state">
        <LoaderCircle className="spin" size={32} />
        <p>Carregando dashboard...</p>
      </main>
    );
  }

  if (error || !bootstrap) {
    return (
      <main className="page-shell centered-state">
        <p className="error-box">{error ?? 'Não foi possível inicializar o dashboard.'}</p>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section className="hero-card">
        <div>
          <span className="eyebrow">Interchange AI</span>
          <h1>Dashboard profissional em Next.js para regras de intercâmbio</h1>
          <p>
            Visualização executiva, filtros globais, comparativos entre bandeiras, simulador e estrutura pronta
            para conexão com API real.
          </p>
        </div>
        <div className="hero-badges">
          <span><Sparkles size={16} /> Next.js</span>
          <span><BarChart3 size={16} /> Recharts</span>
          <span><ShieldCheck size={16} /> Mock/API ready</span>
        </div>
      </section>

      <section className="dashboard-grid">
        <aside className="filter-panel">
          <div className="panel-header">
            <div>
              <p className="panel-title"><Filter size={16} /> Filtros globais</p>
              <span className="panel-subtitle">{filteredRules.length} de {rules.length} regras visíveis</span>
            </div>
          </div>

          <FilterGroup
            title="Bandeiras"
            values={bootstrap.availableFilters.networks}
            selected={selectedNetworks}
            onToggle={(value) => toggleFilter(selectedNetworks, setSelectedNetworks, value)}
          />

          <FilterGroup
            title="Família de cartão"
            values={bootstrap.availableFilters.cardFamilies}
            selected={selectedCardFamilies}
            onToggle={(value) => toggleFilter(selectedCardFamilies, setSelectedCardFamilies, value)}
          />

          <FilterGroup
            title="Tipo de regra"
            values={bootstrap.availableFilters.ruleTypes}
            selected={selectedRuleTypes}
            onToggle={(value) => toggleFilter(selectedRuleTypes, setSelectedRuleTypes, value)}
          />

          <div className="filter-block">
            <label htmlFor="confidence">Score mínimo de confiança</label>
            <input
              id="confidence"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(event) => setMinConfidence(Number(event.target.value))}
            />
            <span className="range-value">{number.format(minConfidence)}</span>
          </div>

          <button type="button" className="secondary-button" onClick={downloadFilteredCsv}>
            <Download size={16} /> Exportar CSV filtrado
          </button>
        </aside>

        <section className="content-area">
          <div className="metrics-grid">
            <MetricCard icon={<CreditCard size={18} />} label="Total de regras" value={String(rules.length)} />
            <MetricCard icon={<ShieldCheck size={18} />} label="Bandeiras" value={String(bootstrap.availableFilters.networks.length)} />
            <MetricCard icon={<BarChart3 size={18} />} label="Tipos de regra" value={String(bootstrap.availableFilters.ruleTypes.length)} />
            <MetricCard icon={<Filter size={18} />} label="Regras filtradas" value={String(filteredRules.length)} />
            <MetricCard icon={<Percent size={18} />} label="Taxa média" value={`${number.format(averageRate)}%`} />
          </div>

          <div className="tabs-row">
            {tabOptions.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={tab.key === activeTab ? 'tab-button active' : 'tab-button'}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'rules' && (
            <section className="section-card">
              <div className="section-heading">
                <div>
                  <h2>Base consolidada de regras</h2>
                  <p>Tabela pronta para exploração, revisão e exportação.</p>
                </div>
              </div>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Bandeira</th>
                      <th>Família</th>
                      <th>Regra</th>
                      <th>Produto</th>
                      <th>Segmento</th>
                      <th>Canal</th>
                      <th>Parcelamento</th>
                      <th>Taxa (%)</th>
                      <th>Fee fixo</th>
                      <th>Confiança</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRules.map((rule) => (
                      <tr key={rule.id}>
                        <td>{rule.network}</td>
                        <td>{rule.card_family}</td>
                        <td>{rule.rule_type}</td>
                        <td>{rule.product}</td>
                        <td>{rule.merchant_group}</td>
                        <td>{rule.channel}</td>
                        <td>{rule.installment_band}</td>
                        <td>{rule.rate_pct !== null ? `${number.format(rule.rate_pct)}%` : '—'}</td>
                        <td>{rule.fixed_fee_amount !== null ? currency.format(rule.fixed_fee_amount) : '—'}</td>
                        <td>
                          <div className="confidence-cell">
                            <div className="confidence-bar">
                              <span style={{ width: `${rule.confidence_score * 100}%` }} />
                            </div>
                            <small>{number.format(rule.confidence_score)}</small>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {activeTab === 'visuals' && (
            <section className="section-card stacked-gap">
              <div className="chart-grid">
                <ChartCard title="Taxa base média por bandeira" subtitle="Apenas regras do tipo base_rate">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={averageByNetwork}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="network" />
                      <YAxis />
                      <Tooltip formatter={(value: number) => `${number.format(value)}%`} />
                      <Bar dataKey="rate_pct" radius={[10, 10, 0, 0]}>
                        {averageByNetwork.map((entry, index) => (
                          <Cell key={entry.network} fill={chartColors[index % chartColors.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>

                <ChartCard title="Distribuição por tipo de regra" subtitle="Volume de registros por classificação">
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie data={distributionByRuleType} dataKey="value" nameKey="name" outerRadius={100} label>
                        {distributionByRuleType.map((entry, index) => (
                          <Cell key={entry.name} fill={chartColors[index % chartColors.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => `${value} regra(s)`} />
                    </PieChart>
                  </ResponsiveContainer>
                </ChartCard>
              </div>

              <ChartCard title="Heatmap de taxa média" subtitle="Bandeira × família de cartão">
                <div className="heatmap-grid">
                  {heatmapData.map((item) => (
                    <div key={`${item.network}-${item.card_family}`} className="heatmap-item">
                      <span>{item.network}</span>
                      <strong>{item.card_family}</strong>
                      <b>{number.format(item.rate_pct)}%</b>
                    </div>
                  ))}
                </div>
              </ChartCard>
            </section>
          )}

          {activeTab === 'products' && (
            <section className="section-card stacked-gap">
              <ChartCard title="Ajustes de parcelamento por faixa" subtitle="Leitura rápida de diferenças entre bandeiras">
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={installmentAdjustments}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="installment_band" />
                    <YAxis />
                    <Tooltip formatter={(value: number) => `${number.format(value)}%`} />
                    <Bar dataKey="rate_pct" fill="#5B7CFA" radius={[10, 10, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>

              <div className="section-heading compact">
                <div>
                  <h2>Comparativo Visa × Mastercard</h2>
                  <p>Taxas base em crédito PF para os produtos disponíveis.</p>
                </div>
              </div>
              <div className="table-wrapper compact-table">
                <table>
                  <thead>
                    <tr>
                      <th>Produto</th>
                      <th>Visa</th>
                      <th>Mastercard</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productComparison.map((item) => (
                      <tr key={item.product}>
                        <td>{item.product}</td>
                        <td>{item.Visa !== undefined ? `${number.format(item.Visa)}%` : '—'}</td>
                        <td>{item.Mastercard !== undefined ? `${number.format(item.Mastercard)}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {activeTab === 'simulator' && (
            <section className="section-card stacked-gap">
              <div className="section-heading">
                <div>
                  <h2>Simulador de taxa de intercâmbio</h2>
                  <p>Modelo pronto para uso local e preparado para troca por backend real.</p>
                </div>
              </div>

              <div className="simulator-grid">
                <SelectField
                  label="Bandeira"
                  value={simulationInput.network}
                  options={bootstrap.availableFilters.networks}
                  onChange={(value) => setSimulationInput((current) => ({ ...current, network: value }))}
                />
                <SelectField
                  label="Família"
                  value={simulationInput.card_family}
                  options={['credit', 'debit', 'prepaid', 'cash_withdrawal']}
                  onChange={(value) =>
                    setSimulationInput((current) => ({ ...current, card_family: value as SimulationInput['card_family'] }))
                  }
                />
                <SelectField
                  label="Público"
                  value={simulationInput.audience}
                  options={['PF', 'PJ', 'ALL']}
                  onChange={(value) =>
                    setSimulationInput((current) => ({ ...current, audience: value as SimulationInput['audience'] }))
                  }
                />
                <SelectField
                  label="Canal"
                  value={simulationInput.channel}
                  options={['cp', 'cnp', 'cp_contactless', 'atm']}
                  onChange={(value) =>
                    setSimulationInput((current) => ({ ...current, channel: value as SimulationInput['channel'] }))
                  }
                />
                <InputField
                  label="Produto"
                  value={simulationInput.product ?? ''}
                  onChange={(value) => setSimulationInput((current) => ({ ...current, product: value }))}
                />
                <InputField
                  label="Segmento"
                  value={simulationInput.merchant_group ?? ''}
                  onChange={(value) => setSimulationInput((current) => ({ ...current, merchant_group: value }))}
                />
                <SelectField
                  label="Parcelamento"
                  value={simulationInput.installment_band ?? 'avista'}
                  options={['avista', '2-6', '7-12', '7-21']}
                  onChange={(value) =>
                    setSimulationInput((current) => ({
                      ...current,
                      installment_band: value === 'avista' ? null : value,
                    }))
                  }
                />
                <InputField
                  label="Valor da transação"
                  type="number"
                  value={String(simulationInput.transaction_amount ?? 0)}
                  onChange={(value) =>
                    setSimulationInput((current) => ({ ...current, transaction_amount: Number(value) }))
                  }
                />
              </div>

              <div>
                <button type="button" className="primary-button" onClick={runSimulation} disabled={simulating}>
                  {simulating ? <><LoaderCircle className="spin" size={16} /> Simulando...</> : 'Executar simulação'}
                </button>
              </div>

              {simulationResult && (
                <>
                  <div className="metrics-grid three-columns">
                    <MetricCard icon={<Percent size={18} />} label="Taxa efetiva" value={`${number.format(simulationResult.total_rate_pct)}%`} />
                    <MetricCard icon={<CreditCard size={18} />} label="Fee fixo" value={currency.format(simulationResult.total_fixed_fee)} />
                    <MetricCard
                      icon={<BarChart3 size={18} />}
                      label="Fee estimado"
                      value={simulationResult.estimated_fee_amount !== null ? currency.format(simulationResult.estimated_fee_amount) : '—'}
                    />
                  </div>

                  <div className="notes-list">
                    {simulationResult.notes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </div>

                  <div className="table-wrapper compact-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Regra aplicada</th>
                          <th>Produto</th>
                          <th>Segmento</th>
                          <th>Canal</th>
                          <th>Parcelamento</th>
                          <th>Taxa</th>
                          <th>Fee fixo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simulationResult.matched_rules.map((rule) => (
                          <tr key={rule.id}>
                            <td>{rule.rule_type}</td>
                            <td>{rule.product}</td>
                            <td>{rule.merchant_group}</td>
                            <td>{rule.channel}</td>
                            <td>{rule.installment_band}</td>
                            <td>{rule.rate_pct !== null ? `${number.format(rule.rate_pct)}%` : '—'}</td>
                            <td>{rule.fixed_fee_amount !== null ? currency.format(rule.fixed_fee_amount) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <ChartCard title="Comparativo rápido entre bandeiras" subtitle="Mesma transação, comparando resposta por rede">
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={comparison}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="network" />
                        <YAxis />
                        <Tooltip formatter={(value: number) => `${number.format(value)}%`} />
                        <Bar dataKey="total_rate_pct" fill="#00B8A9" radius={[10, 10, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>
                </>
              )}
            </section>
          )}

          {activeTab === 'regulatory' && (
            <section className="section-card stacked-gap">
              <div className="section-heading">
                <div>
                  <h2>Análise regulatória e estrutura de referência</h2>
                  <p>
                    Área preparada para consolidar regras do BCB e comparativos regulatórios. Nesta versão, ela
                    mostra o mesmo racional do dashboard original com foco em leitura executiva.
                  </p>
                </div>
              </div>

              <div className="regulatory-grid">
                <div className="reference-card">
                  <h3>Referências configuradas no dashboard atual</h3>
                  <ul>
                    <li>Débito doméstico: referência de teto percentual.</li>
                    <li>Débito de baixo valor: referência de teto nominal por transação.</li>
                    <li>Pré-pago doméstico: referência de teto percentual.</li>
                    <li>Crédito PF: comparação sem teto fixo na visualização atual.</li>
                  </ul>
                </div>
                <div className="reference-card">
                  <h3>Diferenças estruturais por bandeira</h3>
                  <ul>
                    <li>Modelo operacional e escopo.</li>
                    <li>Limite de parcelamento configurado.</li>
                    <li>Suporte a autenticação forte e contactless.</li>
                    <li>Visão pronta para expansão com API regulatória.</li>
                  </ul>
                </div>
              </div>

              <ChartCard title="Débito vs. linha de referência regulatória" subtitle="Comparativo visual das taxas base de débito">
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={debitReference}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="network" />
                    <YAxis />
                    <Tooltip formatter={(value: number) => `${number.format(value)}%`} />
                    <Bar dataKey="rate_pct" fill="#9C6ADE" radius={[10, 10, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="inline-note">Linha de referência sugerida para o dashboard: 0,50%.</div>
              </ChartCard>
            </section>
          )}
        </section>
      </section>
    </main>
  );
}

function FilterGroup({
  title,
  values,
  selected,
  onToggle,
}: {
  title: string;
  values: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <div className="filter-block">
      <p>{title}</p>
      <div className="chip-list">
        {values.map((value) => {
          const active = selected.includes(value);
          return (
            <button
              key={value}
              type="button"
              className={active ? 'filter-chip active' : 'filter-chip'}
              onClick={() => onToggle(value)}
            >
              {value}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <article className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <article className="chart-card">
      <div className="chart-card-header">
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
      {children}
    </article>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="field-block">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function InputField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'number';
}) {
  return (
    <label className="field-block">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
