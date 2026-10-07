import { useEffect, useRef, useState } from "react";
import { acquireThumbnailSlot } from "../utils/thumbnailLoadQueue";

type LazyThumbnailProps = {
  src: string;
  alt: string;
  className?: string;
  placeholderClassName?: string;
};

export function LazyThumbnail({
  src,
  alt,
  className,
  placeholderClassName = "photograph-placeholder",
}: LazyThumbnailProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const releaseRef = useRef<(() => void) | null>(null);
  const retryCountRef = useRef(0);
  const [inView, setInView] = useState(false);
  const [displaySrc, setDisplaySrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    retryCountRef.current = 0;
    setDisplaySrc(null);
    setFailed(false);
    if (releaseRef.current) {
      releaseRef.current();
      releaseRef.current = null;
    }
  }, [src]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) {
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
        }
      },
      { root: null, rootMargin: "150px", threshold: 0.01 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!inView || !src || displaySrc !== null || failed) {
      return;
    }

    let cancelled = false;
    void acquireThumbnailSlot().then((release) => {
      if (cancelled) {
        release();
        return;
      }
      releaseRef.current = release;
      setDisplaySrc(src);
    });

    return () => {
      cancelled = true;
    };
  }, [inView, src, displaySrc, failed]);

  useEffect(() => {
    return () => {
      if (releaseRef.current) {
        releaseRef.current();
        releaseRef.current = null;
      }
    };
  }, []);

  const releaseSlot = () => {
    if (releaseRef.current) {
      releaseRef.current();
      releaseRef.current = null;
    }
  };

  const handleLoad = () => {
    releaseSlot();
  };

  const handleError = () => {
    if (retryCountRef.current < 1) {
      retryCountRef.current += 1;
      releaseSlot();
      setDisplaySrc(null);
      const retrySrc = `${src}${src.includes("?") ? "&" : "?"}_retry=${retryCountRef.current}`;
      window.setTimeout(() => {
        void acquireThumbnailSlot().then((release) => {
          releaseRef.current = release;
          setDisplaySrc(retrySrc);
        });
      }, 300);
      return;
    }
    releaseSlot();
    setFailed(true);
  };

  return (
    <div ref={rootRef} className="lazy-thumbnail">
      {displaySrc && !failed ? (
        <img
          src={displaySrc}
          alt={alt}
          className={className}
          loading="lazy"
          decoding="async"
          onLoad={handleLoad}
          onError={handleError}
        />
      ) : failed ? (
        <div className={placeholderClassName}>No Image</div>
      ) : (
        <div className={placeholderClassName} aria-hidden="true" />
      )}
    </div>
  );
}
