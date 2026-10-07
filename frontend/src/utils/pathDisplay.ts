/** Shorten a filesystem path with a middle ellipsis, e.g. `beginning/of/.../picture.NEF`. */
export function truncatePathMiddle(path: string, maxLength = 48): string {
  if (path.length <= maxLength) {
    return path;
  }
  const ellipsis = "/.../";
  const budget = maxLength - ellipsis.length;
  if (budget <= 0) {
    return path.slice(0, maxLength);
  }
  const headLen = Math.ceil(budget / 2);
  const tailLen = Math.floor(budget / 2);
  return `${path.slice(0, headLen)}${ellipsis}${path.slice(-tailLen)}`;
}
