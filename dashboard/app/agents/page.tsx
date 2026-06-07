// dashboard/app/agents/page.tsx
/**
 * Agent Performance Dashboard: Per-agent win rates, confidence multipliers, trending
 */
'use client';

import { useEffect, useState } from 'react';
import useSWR from 'swr';

interface AgentStats {
  agent: string;
  regime: string;
  total_signals: number;
  winning_signals: number;
  losing_signals: number;
  win_rate: number;
  confidence_multiplier: number;
  last_updated: string;
}

const AGENTS = [
  'technical',
  'sentiment',
  'macro',
  'research',
  'news_momentum',
  'vwap',
  'supply_demand',
];

const REGIMES = ['expansion', 'crisis', 'pandemic'];

export default function AgentsPage() {
  const { data: stats, isLoading } = useSWR('/api/analytics/agent-stats', async (url) => {
    const res = await fetch(url);
    return res.json();
  }, { refreshInterval: 60000 });

  const getConfidenceColor = (multiplier: number) => {
    if (multiplier >= 1.2) return 'text-green-600 bg-green-50';
    if (multiplier >= 1.0) return 'text-blue-600 bg-blue-50';
    if (multiplier >= 0.8) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getWinRateColor = (winRate: number) => {
    if (winRate >= 0.65) return 'text-green-600';
    if (winRate >= 0.55) return 'text-blue-600';
    if (winRate >= 0.45) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6 p-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Agent Performance</h1>
        <p className="text-gray-500">Monitor per-agent accuracy and confidence adjustments by market regime</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm font-medium text-gray-600">Total Agents</div>
          <div className="text-3xl font-bold mt-2 text-blue-600">{AGENTS.length}</div>
          <div className="text-xs text-gray-500 mt-2">Active analysis agents</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm font-medium text-gray-600">Total Signals</div>
          <div className="text-3xl font-bold mt-2 text-purple-600">
            {stats?.stats?.reduce((sum: number, s: AgentStats) => sum + s.total_signals, 0) || '—'}
          </div>
          <div className="text-xs text-gray-500 mt-2">All signals generated</div>
        </div>

        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm font-medium text-gray-600">Avg Win Rate</div>
          <div className="text-3xl font-bold mt-2 text-green-600">
            {stats?.stats ? (
              (stats.stats.reduce((sum: number, s: AgentStats) => sum + s.win_rate, 0) / stats.stats.length * 100).toFixed(1)
            ) : '—'}%
          </div>
          <div className="text-xs text-gray-500 mt-2">Across all agents</div>
        </div>
      </div>

      {/* Agent Performance by Regime */}
      {REGIMES.map((regime) => (
        <div key={regime} className="bg-white p-6 rounded-lg border border-gray-200">
          <h2 className="text-xl font-bold mb-4 capitalize">{regime} Regime</h2>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="text-left py-3 px-4 font-semibold">Agent</th>
                  <th className="text-right py-3 px-4 font-semibold">Signals</th>
                  <th className="text-right py-3 px-4 font-semibold">Won</th>
                  <th className="text-right py-3 px-4 font-semibold">Lost</th>
                  <th className="text-right py-3 px-4 font-semibold">Win Rate</th>
                  <th className="text-center py-3 px-4 font-semibold">Confidence</th>
                  <th className="text-center py-3 px-4 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {AGENTS.map((agent) => {
                  const agentStats = stats?.stats?.find(
                    (s: AgentStats) => s.agent === agent && s.regime === regime
                  );

                  return (
                    <tr key={`${agent}-${regime}`} className="border-b hover:bg-gray-50">
                      <td className="py-3 px-4 font-medium capitalize">{agent}</td>
                      <td className="py-3 px-4 text-right">{agentStats?.total_signals || 0}</td>
                      <td className="py-3 px-4 text-right text-green-600 font-semibold">
                        {agentStats?.winning_signals || 0}
                      </td>
                      <td className="py-3 px-4 text-right text-red-600 font-semibold">
                        {agentStats?.losing_signals || 0}
                      </td>
                      <td className={`py-3 px-4 text-right font-bold ${
                        getWinRateColor(agentStats?.win_rate || 0)
                      }`}>
                        {((agentStats?.win_rate || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-block px-3 py-1 rounded font-semibold ${
                          getConfidenceColor(agentStats?.confidence_multiplier || 1)
                        }`}>
                          {(agentStats?.confidence_multiplier || 1).toFixed(2)}x
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        {!agentStats ? (
                          <span className="text-gray-400 text-xs">No data</span>
                        ) : agentStats.confidence_multiplier >= 1.2 ? (
                          <span className="text-green-600 text-xs font-semibold">⬆️ Boost</span>
                        ) : agentStats.confidence_multiplier >= 0.9 ? (
                          <span className="text-blue-600 text-xs font-semibold">→ Neutral</span>
                        ) : (
                          <span className="text-red-600 text-xs font-semibold">⬇️ Reduce</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Confidence Multiplier Explanation */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-6 rounded-lg border border-blue-200">
        <h3 className="font-bold mb-3">How Confidence Multipliers Work</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="font-semibold text-green-700">1.3x (Boost)</div>
            <p className="text-gray-700 mt-1">Win rate ≥ 70%. Signal confidence increased.</p>
          </div>
          <div>
            <div className="font-semibold text-blue-700">1.1x (Modest Boost)</div>
            <p className="text-gray-700 mt-1">Win rate 60-70%. Small confidence increase.</p>
          </div>
          <div>
            <div className="font-semibold text-yellow-700">1.0x (Neutral)</div>
            <p className="text-gray-700 mt-1">Win rate 45-60%. No adjustment.</p>
          </div>
          <div>
            <div className="font-semibold text-red-700">0.6x-0.8x (Reduce)</div>
            <p className="text-gray-700 mt-1">Win rate &lt; 45%. Signal confidence reduced.</p>
          </div>
        </div>
      </div>

      {/* Signal Distribution */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h2 className="text-xl font-bold mb-4">Signal Distribution by Type</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 border rounded-lg">
            <div className="text-sm text-gray-600">Bullish Signals</div>
            <div className="text-2xl font-bold text-green-600 mt-2">
              {stats?.stats
                ?.filter((s: AgentStats) => s.winning_signals > 0)
                .reduce((sum: number, s: AgentStats) => sum + s.winning_signals, 0) || 0}
            </div>
          </div>
          <div className="p-4 border rounded-lg">
            <div className="text-sm text-gray-600">Bearish Signals</div>
            <div className="text-2xl font-bold text-red-600 mt-2">
              {stats?.stats
                ?.filter((s: AgentStats) => s.losing_signals > 0)
                .reduce((sum: number, s: AgentStats) => sum + s.losing_signals, 0) || 0}
            </div>
          </div>
          <div className="p-4 border rounded-lg">
            <div className="text-sm text-gray-600">Total Generated</div>
            <div className="text-2xl font-bold text-blue-600 mt-2">
              {stats?.stats?.reduce((sum: number, s: AgentStats) => sum + s.total_signals, 0) || 0}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
