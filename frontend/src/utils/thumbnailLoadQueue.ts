/** Limits concurrent browser thumbnail fetches across the app. */

const MAX_CONCURRENT = 6;

let activeLoads = 0;
const waitQueue: Array<() => void> = [];

export function acquireThumbnailSlot(): Promise<() => void> {
  return new Promise((resolve) => {
    const grant = () => {
      activeLoads += 1;
      resolve(() => {
        activeLoads -= 1;
        const next = waitQueue.shift();
        if (next) {
          next();
        }
      });
    };
    if (activeLoads < MAX_CONCURRENT) {
      grant();
    } else {
      waitQueue.push(grant);
    }
  });
}
