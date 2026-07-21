export function formatBytes(bytes) {
  if (!bytes || bytes < 1024) return `${bytes || 0} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = bytes / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`
}

export const GB = 1024 ** 3
export const bytesToGb = (bytes) => +(bytes / GB).toFixed(2)
export const gbToBytes = (gb) => Math.round(gb * GB)
