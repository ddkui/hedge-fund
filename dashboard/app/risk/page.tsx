// dashboard/app/risk/page.tsx
/**
 * Risk Dashboard: Circuit breaker status, drawdown curve, hedges, broker health
 */
'use client';

import { useEffect, useState } from 'react';
import useSWR from 'swr';

interface PortfolioSnapshot {
  timestamp: string;
  total_value: number;
  peak_value: number;
  cash: number;
  drawdown_pct: number;
}

interface HedgeStatus {
  correlation: number;
  hedge_active: boolean;
  hedge_qty: number;
  recent_activity: Array<{
    action: string;
    correlation: number;
    created_at: string;
  }>;
}

interface RiskMetrics {
  circuit_breaker_tripped: boolean;
  max_drawdown: number;
  portfolio_value: number;
  correlation_to_spy: number;
}

export default function RiskDashboard() {
  const { data: metrics } = useSWR('/api/risk/metrics', async (url) => {
    const res = await fetch(url);
    return res.json();
  }, { refreshInterval: 30000 });

  const { data: hedgeStatus } = useSWR('/api/analytics/correlation-hedge/status', async (url) => {
    const res = await fetch(url);
    return res.json();
  }, { refreshInterval: 60000 });

  const { data: portfolioHistory } = useSWR('/api/risk/portfolio-history', async (url) => {
    const res = await fetch(url);
    return res.json();
  }, { refreshInterval: 60000 });

  const circuitBreakerStatus = metrics?.circuit_breaker_tripped;
  const maxDrawdown = metrics?.max_drawdown ?? 0;
  const correlation = hedgeStatus?.correlation ?? 0;

  return (
    <div className="space-y-6 p-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold">Risk Management</h1>
        <p className="text-gray-500">Monitor portfolio risk, hedges, and circuit breaker status</p>
      </div>

      {/* Top Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Circuit Breaker Status */}
        <div className={`p-4 rounded-lg border-2 ${
          circuitBreakerStatus ? 'border-red-500 bg-red-50' : 'border-green-500 bg-green-50'
        }`}>
          <div className="text-sm font-medium text-gray-600">Circuit Breaker</div>
          <div className={`text-3xl font-bold mt-2 ${
            circuitBreakerStatus ? 'text-red-600' : 'text-green-600'
          }`}>
            {circuitBreakerStatus ? '🚨 TRIPPED' : '✅ OK'}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {circuitBreakerStatus ? 'Trading halted at max loss' : 'Limit: 5% daily loss'}
          </div>
        </div>

        {/* Max Drawdown */}
        <div className={`p-4 rounded-lg border-2 border-blue-300 bg-blue-50`}>
          <div className="text-sm font-medium text-gray-600">Max Drawdown</div>
          <div className={`text-3xl font-bold mt-2 ${
            maxDrawdown > 15 ? 'text-orange-600' : 'text-blue-600'
          }`}>
            {maxDrawdown.toFixed(2)}%
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {maxDrawdown > 20 ? '⚠️ Approaching limit (20%)' : 'Within limits'}
          </div>
        </div>

        {/* SPY Correlation */}
        <div className={`p-4 rounded-lg border-2 ${
          correlation > 0.8 ? 'border-orange-500 bg-orange-50' : 'border-yellow-300 bg-yellow-50'
        }`}>
          <div className="text-sm font-medium text-gray-600">SPY Correlation</div>
          <div className={`text-3xl font-bold mt-2 ${
            correlation > 0.8 ? 'text-orange-600' : 'text-yellow-600'
          }`}>
            {correlation.toFixed(3)}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {correlation > 0.8 ? '🛡️ Hedge active' : 'Threshold: 0.8'}
          </div>
        </div>

        {/* Hedge Status */}
        <div className={`p-4 rounded-lg border-2 ${
          hedgeStatus?.hedge_active ? 'border-purple-500 bg-purple-50' : 'border-gray-300 bg-gray-50'
        }`}>
          <div className="text-sm font-medium text-gray-600">Active Hedges</div>
          <div className={`text-3xl font-bold mt-2 ${
            hedgeStatus?.hedge_active ? 'text-purple-600' : 'text-gray-600'
          }`}>
            {hedgeStatus?.hedge_active ? hedgeStatus.hedge_qty.toFixed(0) : '0'} SPY
          </div>
          <div className="text-xs text-gray-500 mt-2">
            {hedgeStatus?.hedge_active ? 'Short position active' : 'No active hedges'}
          </div>
        </div>
      </div>

      {/* Drawdown Curve */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h2 className="text-xl font-bold mb-4">Portfolio Drawdown Curve (30 Days)</h2>
        <div className="h-64 bg-gradient-to-br from-gray-50 to-gray-100 rounded flex items-center justify-center">
          {/* TODO: Integrate Chart.js or Recharts for actual chart */}
          <div className="text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Drawdown chart loading...
          </div>
        </div>
      </div>

      {/* Hedge Activity History */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h2 className="text-xl font-bold mb-4">Hedge Activity (Last 30 Days)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b">
              <tr>
                <th className="text-left py-3 px-4 font-semibold">Time</th>
                <th className="text-left py-3 px-4 font-semibold">Action</th>
                <th className="text-right py-3 px-4 font-semibold">Correlation</th>
                <th className="text-right py-3 px-4 font-semibold">SPY Price</th>
                <th className="text-right py-3 px-4 font-semibold">Quantity</th>
              </tr>
            </thead>
            <tbody>
              {hedgeStatus?.recent_activity?.map((activity, i) => (
                <tr key={i} className="border-b hover:bg-gray-50">
                  <td className="py-3 px-4">
                    {new Date(activity.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-block px-3 py-1 rounded text-xs font-semibold ${
                      activity.action === 'activate' ? 'bg-purple-100 text-purple-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {activity.action.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">{activity.correlation.toFixed(3)}</td>
                  <td className="py-3 px-4 text-right">${activity.spy_price?.toFixed(2) || 'N/A'}</td>
                  <td className="py-3 px-4 text-right font-semibold">{activity.hedge_qty?.toFixed(0) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!hedgeStatus?.recent_activity || hedgeStatus.recent_activity.length === 0 && (
            <div className="py-8 text-center text-gray-400">No hedge activity yet</div>
          )}
        </div>
      </div>

      {/* Risk Alerts */}
      <div className="bg-white p-6 rounded-lg border border-gray-200">
        <h2 className="text-xl font-bold mb-4">Risk Alerts</h2>
        <div className="space-y-3">
          {circuitBreakerStatus && (
            <div className="p-4 bg-red-50 border border-red-300 rounded-lg">
              <div className="font-semibold text-red-800">🚨 Circuit Breaker Active</div>
              <p className="text-sm text-red-700 mt-1">
                Trading has been halted due to exceeding the 5% daily loss limit.
                Manual review required before resuming. Will auto-reset at 23:59.
              </p>
            </div>
          )}

          {maxDrawdown > 15 && (
            <div className="p-4 bg-orange-50 border border-orange-300 rounded-lg">
              <div className="font-semibold text-orange-800">⚠️ High Drawdown</div>
              <p className="text-sm text-orange-700 mt-1">
                Portfolio drawdown is {maxDrawdown.toFixed(2)}%. Approaching 20% limit.
              </p>
            </div>
          )}

          {correlation > 0.8 && (
            <div className="p-4 bg-purple-50 border border-purple-300 rounded-lg">
              <div className="font-semibold text-purple-800">🛡️ SPY Hedge Active</div>
              <p className="text-sm text-purple-700 mt-1">
                Portfolio correlation to SPY ({correlation.toFixed(3)}) exceeds 0.8.
                Short hedge active for risk reduction.
              </p>
            </div>
          )}

          {!circuitBreakerStatus && maxDrawdown <= 15 && correlation <= 0.8 && (
            <div className="p-4 bg-green-50 border border-green-300 rounded-lg">
              <div className="font-semibold text-green-800">✅ All Clear</div>
              <p className="text-sm text-green-700 mt-1">
                No active risk alerts. Portfolio is within all risk limits.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
