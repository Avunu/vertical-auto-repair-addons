/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The stage, sized to an element and scaled to fill it. The stage is at
 * least 1920x1080 and has the element's shape: a 16:9 TV gets exactly that,
 * a 4:3 iPad a taller stage (1920x1440), an ultrawide a wider one. So a
 * screen never has empty bars, and a taller one has room for more cards.
 */
import {useEffect, useRef, useState} from "react";

const MIN = {width: 1920, height: 1080};

export interface Fit {
  scale: number;
  width: number;
  height: number;
}

export function fitStage(width: number, height: number): Fit {
  if (width <= 0 || height <= 0) {
    return {scale: 1, ...MIN};
  }
  const aspect = width / height;
  const wide = aspect >= MIN.width / MIN.height;
  const stage = wide
    ? {width: Math.round(MIN.height * aspect), height: MIN.height}
    : {width: MIN.width, height: Math.round(MIN.width / aspect)};
  return {scale: width / stage.width, ...stage};
}

export function useFit<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [fit, setFit] = useState<Fit>({scale: 1, ...MIN});
  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return undefined;
    }
    const measure = () => setFit(fitStage(el.clientWidth, el.clientHeight));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return {ref, ...fit};
}
