import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 存档 · 读档 —— 对齐 game/ui/panels_meta.py::_panel_save_load（L22）
// 槽位列表 + 保存/读档（client.saveSlots / save / load）。
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function asNum(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : def;
}

function slotLabel(s: Dict): string {
  if (s.empty === true) {
    return `[${asNum(s.slot)}] 空槽位`;
  }
  return `[${asNum(s.slot)}] ${asStr(s.time)} | ${asStr(s.era)}${asNum(s.year)}年${asNum(s.month)}月`;
}

export default function SavePanel() {
  const setState = useGameStore((s) => s.setState);
  const popOverlay = useGameStore((s) => s.popOverlay);
  const [slots, setSlots] = useState<Dict[] | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [busy, setBusy] = useState<"save" | "load" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().saveSlots();
        if (alive) setSlots((res.slots as Dict[]) ?? []);
      } catch (e) {
        console.error("[save_slots]", e);
        if (alive) {
          setSlots([]);
          setMsg("槽位读取失败：" + (e instanceof Error ? e.message : String(e)));
        }
      }
    })();
    return () => { alive = false; };
  }, []);

  async function doSave() {
    if (busy || sel === null || !slots) {
      setMsg("请选择槽位。");
      return;
    }
    setBusy("save");
    setMsg(null);
    try {
      const res = await getApiClient().save(asNum(slots[sel].slot, 1));
      setMsg(res.ok ? `已保存至槽位 ${res.slot}。` : "存档失败。");
      const refreshed = await getApiClient().saveSlots();
      setSlots((refreshed.slots as Dict[]) ?? []);
    } catch (e) {
      console.error("[save]", e);
      setMsg("存档失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(null);
    }
  }

  async function doLoad() {
    if (busy || sel === null || !slots) {
      setMsg("请选择槽位。");
      return;
    }
    if (slots[sel].empty === true) {
      setMsg("该槽位为空。");
      return;
    }
    setBusy("load");
    setMsg(null);
    try {
      const res = await getApiClient().load(asNum(slots[sel].slot, 1));
      setState(res.state);
      setMsg("读档完成，江山重续。");
      popOverlay();
    } catch (e) {
      console.error("[load]", e);
      setMsg("读档失败，存档可能已损坏：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
        {slots === null ? (
          <p className="flex items-center justify-center gap-2 py-8 text-sm text-dim">
            <Loader2 size={14} className="animate-spin" /> 槽位读取中…
          </p>
        ) : (
          <div className="space-y-1">
            {slots.map((s, i) => (
              <button
                key={i}
                onClick={() => setSel(i)}
                className={`block w-full rounded px-3 py-2 text-left text-sm transition ${
                  sel === i ? "bg-red text-paper" : "text-ink hover:bg-gold-light"
                }`}
              >
                {slotLabel(s)}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="flex justify-center gap-4">
        <button
          onClick={doSave}
          disabled={busy !== null}
          className="flex items-center gap-2 rounded-lg bg-red px-8 py-2.5 font-kai text-base tracking-[0.3em] text-paper transition hover:bg-red-dark disabled:opacity-60"
        >
          {busy === "save" && <Loader2 size={16} className="animate-spin" />}
          保 存
        </button>
        <button
          onClick={doLoad}
          disabled={busy !== null}
          className="flex items-center gap-2 rounded-lg bg-red px-8 py-2.5 font-kai text-base tracking-[0.3em] text-paper transition hover:bg-red-dark disabled:opacity-60"
        >
          {busy === "load" && <Loader2 size={16} className="animate-spin" />}
          读 档
        </button>
      </div>
      {msg && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="text-sm leading-relaxed text-ink">{msg}</p>
        </div>
      )}
    </div>
  );
}
