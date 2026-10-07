import type { Photograph } from "../types";

/** Tooltip text when photograph ID/checksum are shown in red (`has_errors`). */
export function photographErrorTooltip(photo: Photograph): string {
  if (!photo.has_errors) {
    return "";
  }

  const hints: string[] = [];
  if (!photo.image_url) {
    hints.push("thumbnail could not be created or loaded");
  }
  if (!photo.checksum) {
    hints.push("checksum could not be computed");
  }
  if (hints.length === 0) {
    hints.push("metadata (EXIF) read or another processing step may have failed");
  }

  return (
    "This photograph is flagged because an error occurred during processing " +
    "(image storage, checksum, or metadata). " +
    `Likely: ${hints.join("; ")}.`
  );
}
