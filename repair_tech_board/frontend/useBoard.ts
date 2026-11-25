/**
 * Copyright 2026 Avunu LLC (avu.nu)
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
 *
 * The board, polled. A failed refresh keeps the last good board on screen
 * and sets `stale`, so a network blip never blanks the shop's TV. A user the
 * ACLs refuse sets `denied` instead: retrying can't fix that, but the TV
 * should say so rather than look offline.
 */
import {useEffect, useState} from "react";
import type {Board} from "./api/api";
import {errorMessage, RpcError} from "./api/client";
import {odoo} from "./odoo";

export const REFRESH_MS = 30_000;

export function useBoard(): {board: Board | null; stale: boolean; denied: boolean} {
  const [board, setBoard] = useState<Board | null>(null);
  const [stale, setStale] = useState(false);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const next = await odoo.call("repair.order", "board_jobs");
        if (alive) {
          setBoard(next);
          setStale(false);
          setDenied(false);
        }
      } catch (error) {
        errorMessage(error); // logs it
        if (alive) {
          setStale(true);
          setDenied(error instanceof RpcError && error.kind === "access");
        }
      }
    };
    void refresh();
    const poll = setInterval(refresh, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, []);

  return {board, stale, denied};
}
