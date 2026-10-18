export function paretoFront(points, xDirection = 'min', yDirection = 'min') {
  const sign = direction => direction === 'max' ? -1 : 1
  const sorted = points.filter(p => p.value.length === 2 && p.value.every(Number.isFinite))
    .map(point => ({point, x: point.value[0] * sign(xDirection), y: point.value[1] * sign(yDirection)}))
    .sort((a, b) => a.x - b.x || a.y - b.y)
  const front = []
  let bestY = Infinity, bestX = Infinity
  for (const {point, x, y} of sorted) {
    if (y < bestY || y === bestY && x === bestX) {
      front.push(point)
      bestX = x
      bestY = y
    }
  }
  return front.sort((a, b) => a.value[0] - b.value[0])
}
