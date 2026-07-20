export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function shortId(value: string): string {
  return value.slice(0, 8);
}

export function compactTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function ratio(value: number): string {
  return `${value.toFixed(value >= 10 ? 0 : 1)}×`;
}
