// Shared display formatting for raw numbers coming from the profile/optimizer
// config and the backend's API responses.

export function formatPercent(value, decimals = 1) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    return `${(Number(value) * 100).toFixed(decimals)}%`;
}

export function formatCurrency(value) {
    if (value == null || Number.isNaN(Number(value))) return "—";
    const n = Number(value);
    const abs = Math.abs(n);
    if (abs >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
    if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(0)}M`;
    if (abs >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
    return `$${n.toFixed(0)}`;
}
