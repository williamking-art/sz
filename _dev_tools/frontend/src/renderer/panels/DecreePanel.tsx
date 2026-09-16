import { useState } from "react";
import { Loader2, Merge, PenLine, Scroll, Send, Sparkles, Stamp, MessageSquare } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 常见拟旨范例模板（点击一键填入）
const DECREE_TEMPLATES = [
  { label: "免灾赈民", text: "敕：两浙、江南诸路频遭水患，特除免今岁夏秋两税积欠，开常平仓出陈粮赈济流民，督办有司毋得迁延。" },
  { label: "开海市舶", text: "敕：广南东路广州市舶司、两浙明州各增置海舶榷场，优假外夷商贾，通互市以阜国用。" },
  { label: "治河防汛", text: "敕：工部遣员督领夫役，修浚黄河故道堤防，拨内帑钱五万贯以佐经费。" },
  { label: "严防北境", text: "敕：河北、河东缘边诸军整肃戎备，加固真定、大名城防，谍探北朝动向，毋得轻举妄动。" },
];

interface ProcDef {
  key: string;
  label: string;
  fields: { key: string; label: string; type: "text" | "number"; def: string }[];
}

const PROCEDURES: ProcDef[] = [
  {
    key: "fixed_finance",
    label: "钱粮调度",
    fields: [
      { key: "source", label: "调出仓府", type: "text", def: "国库" },
      { key: "target", label: "拨往去处", type: "text", def: "开封府" },
      { key: "amount", label: "拨发数额（贯/石）", type: "number", def: "20000" }
    ]
  },
  {
    key: "fixed_tech",
    label: "军工科技",
    fields: [
      { key: "project", label: "营缮项目", type: "text", def: "改良水运翻车" },
      { key: "invest", label: "度支投入（贯）", type: "number", def: "10000" },
      { key: "months", label: "督造工期（月）", type: "number", def: "6" }
    ]
  },
  {
    key: "fixed_construction",
    label: "水利营造",
    fields: [
      { key: "site", label: "营建州郡", type: "text", def: "扬州" },
      { key: "kind", label: "工程门类", type: "text", def: "疏浚运河" },
      { key: "invest", label: "调拨工费（贯）", type: "number", def: "20000" },
      { key: "months", label: "预计工期（月）", type: "number", def: "12" }
    ]
  },
  {
    key: "fixed_army",
    label: "边防调戍",
    fields: [
      { key: "army", label: "移防军号", type: "text", def: "殿前司捧日军" },
      { key: "to_line", label: "驻防阵线", type: "text", def: "北线_真定河间" },
      { key: "scale", label: "调发兵额（人）", type: "number", def: "2000" }
    ]
  }
];

export default function DecreePanel() {
  const [mode, setMode] = useState<"free" | "fixed" | "review" | "kouyu">("free");
  // 自由拟旨输入
  const [freeText, setFreeText] = useState("");
  const [title, setTitle] = useState("");
  const [minister, setMinister] = useState("");
  const [secret, setSecret] = useState(false);

  // 口谕输入
  const [kouyuTitle, setKouyuTitle] = useState("");
  const [kouyuText, setKouyuText] = useState("");
  const [kouyuPrestige, setKouyuPrestige] = useState("微");
  const [kouyuSat, setKouyuSat] = useState("微");
  const [kouyuTax, setKouyuTax] = useState("");

  // 固定政务输入
  const [cat, setCat] = useState(PROCEDURES[0].key);
  const [fixedValues, setFixedValues] = useState<Record<string, string>>({});

  // 票拟批红（诏草审批）
  const state = useGameStore((s) => s.state);
  const [draftSel, setDraftSel] = useState<Set<string>>(new Set());
  const [detailId, setDetailId] = useState<string | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [revBusy, setRevBusy] = useState(false);

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);

  const proc = PROCEDURES.find((p) => p.key === cat)!;

  function valOf(f: ProcDef["fields"][number]): string {
    return fixedValues[`${cat}.${f.key}`] ?? f.def;
  }

  async function submitFree() {
    if (busy || !freeText.trim()) return;
    setBusy(true);
    setResult(null);

    try {
      const res = await getApiClient().action("issue_decree", {
        text: freeText.trim(),
        title: title.trim() || "御前诏敕",
        minister: minister.trim() || "有司",
        is_secret: secret
      });
      if (res.state) setState(res.state);
      setResult(res.message || "诏敕已传宣尚书省，有司领旨奉行。");
      setFreeText("");
      setTitle("");
    } catch (e) {
      console.error("[issue_decree]", e);
      try {
        const fallbackRes = await getApiClient().action("issue_free_decree", {
          parse_result: {
            category: "custom",
            exec_mode: "instant",
            title: title.trim() || "御前特旨",
            text: freeText.trim()
          },
          minister: minister.trim() || "中书门下",
          is_secret: secret
        });
        if (fallbackRes.state) setState(fallbackRes.state);
        setResult(fallbackRes.message || "圣旨已下发中枢门下，候朝堂推演施行。");
        setFreeText("");
      } catch (err2) {
        setResult("拟旨未成：" + (e instanceof Error ? e.message : String(e)));
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitKouyu() {
    if (busy || !kouyuText.trim()) return;
    setBusy(true);
    setResult(null);
    const effects: Record<string, unknown>[] = [];
    if (kouyuPrestige && kouyuPrestige !== "无") {
      effects.push({ dim: "prestige", tier: kouyuPrestige });
    }
    if (kouyuSat && kouyuSat !== "无") {
      effects.push({ dim: "population_satisfaction", tier: kouyuSat });
    }
    const taxRate = Number(kouyuTax);
    if (kouyuTax !== "" && Number.isFinite(taxRate) && taxRate > 0 && taxRate <= 1) {
      effects.push({ dim: "commerce_tax", value: taxRate });
    }
    try {
      const res = await getApiClient().action("issue_kouyu", {
        title: kouyuTitle.trim() || "口谕",
        body: kouyuText.trim(),
        effects,
      });
      if (res.state) setState(res.state);
      setResult(res.message || "口宣已传，效力稍弱，或失本意。");
      setKouyuTitle("");
      setKouyuText("");
    } catch (e) {
      setResult("口谕未成：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  async function submitFixed() {
    if (busy) return;
    setBusy(true);
    setResult(null);
    const params: Record<string, string | number> = {};
    for (const f of proc.fields) {
      const raw = valOf(f);
      params[f.key] = f.type === "number" ? Number(raw || 0) : raw;
    }
    const parseResult = {
      category: cat,
      exec_mode: "longterm",
      title: title.trim() || proc.label,
      params
    };
    try {
      const res = await getApiClient().action("issue_free_decree", {
        parse_result: parseResult,
        minister: minister.trim() || "有司",
        is_secret: secret
      });
      if (res.state) setState(res.state);
      setResult(res.message || "旨意已成定例，列入在办政务。");
    } catch (e) {
      console.error("[issue_fixed]", e);
      setResult("颁行政务失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  // ---- 票拟批红：和解锁 / 会签 / 审批 ----
  const drafts: Record<string, unknown>[] = Array.isArray(state?.edict_drafts)
    ? (state!.edict_drafts as Record<string, unknown>[])
    : [];
  const detailDraft = drafts.find((d) => d.id === detailId) ?? null;

  function toggleDraft(id: string) {
    setDraftSel((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openDetail(id: string) {
    if (revBusy) return;
    setDetailId(id);
    setReview(null);
    setReviewing(true);
    getApiClient()
      .councilReview(id)
      .then((res) => setReview(res.review as Record<string, unknown>))
      .catch((e) => {
        console.error("[council_review]", e);
        setReview({
          memo: "（会签失败）", objections: "（门下省未见条目）",
          executions: "（六部俟旨）", verdict: "—"
        });
      })
      .finally(() => setReviewing(false));
  }

  async function reviewAction(decision: "approve" | "force") {
    if (revBusy || !detailId) return;
    setRevBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("issue_edict_from_review", { draft_id: detailId, decision });
      if (res.state) setState(res.state);
      setResult(res.message || "诏令已下。");
      setDetailId(null); setReview(null);
      setDraftSel((prev) => { const n = new Set(prev); n.delete(detailId!); return n; });
    } catch (e) {
      setResult("批红失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setRevBusy(false);
    }
  }

  async function rejectDraft() {
    if (revBusy || !detailId) return;
    setRevBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("reject_edict_draft", { draft_id: detailId });
      if (res.state) setState(res.state);
      setResult(res.message || "已打回诏草。");
      setDetailId(null); setReview(null);
      setDraftSel((prev) => { const n = new Set(prev); n.delete(detailId!); return n; });
    } catch (e) {
      setResult("打回失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setRevBusy(false);
    }
  }

  async function mergeDrafts() {
    if (revBusy || draftSel.size < 2) return;
    setRevBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().action("merge_drafts", { draft_ids: [...draftSel] });
      if (res.state) setState(res.state);
      setResult(res.message || "诏书已成。");
      setDraftSel(new Set()); setDetailId(null); setReview(null);
    } catch (e) {
      setResult("汇成失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setRevBusy(false);
    }
  }

  const rev = (k: string) => (review ? String(review[k] ?? "") : "");

  // 迁移补齐（原 Tk `_panel_decree_entry`）：知制诰润色 / 批改诏草、弃删诏草 —— 走 /api/decree/*
  const [polishBusy, setPolishBusy] = useState(false);

  async function polishDraft(id: string) {
    if (polishBusy || revBusy) return;
    const d = drafts.find((x) => x.id === id);
    if (!d) return;
    setPolishBusy(true);
    setResult(null);
    try {
      // 批改：以现有正文为诏意，AI 润色后回写该诏草（后端清会签缓存 → 重入待签）
      const res = await getApiClient().polishDecree(String(d.body ?? ""), id);
      if (res.state) setState(res.state);
      const nd = (res.draft ?? {}) as Record<string, unknown>;
      setResult(`知制诰润色已毕，「${String(nd.title ?? d.title ?? "")}」重入待签。`);
      setDetailId(null);
      setReview(null);
    } catch (e) {
      console.error("[decree/polish]", e);
      setResult("润色失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setPolishBusy(false);
    }
  }

  async function discardDraft(id: string) {
    if (polishBusy || revBusy) return;
    setPolishBusy(true);
    setResult(null);
    try {
      const res = await getApiClient().discardDecreeDraft(id);
      if (res.state) setState(res.state);
      setResult(`已弃删诏草「${res.title ?? ""}」。`);
      if (detailId === id) {
        setDetailId(null);
        setReview(null);
      }
      setDraftSel((prev) => {
        const n = new Set(prev);
        n.delete(id);
        return n;
      });
    } catch (e) {
      console.error("[decree/discard]", e);
      setResult("弃删失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setPolishBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* 模式切换：亲笔拟旨 / 常设政务 */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex gap-2">
          <button
            onClick={() => setMode("free")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "free"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <PenLine size={14} /> 亲笔拟旨
          </button>
          <button
            onClick={() => setMode("fixed")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "fixed"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Scroll size={14} /> 常设政务
          </button>
          <button
            onClick={() => setMode("review")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "review"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Stamp size={14} /> 票拟批红
            {drafts.length > 0 && (
              <span className="ml-0.5 rounded-full bg-goldDark/20 px-1.5 text-[10px] leading-4 text-ink-light">
                {drafts.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setMode("kouyu")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "kouyu"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <MessageSquare size={14} /> 口 谕
          </button>
        </div>
        <span className="font-kai text-xs text-dim">
          {mode === "free"
            ? "乾纲独断 · 言出法随"
            : mode === "fixed"
              ? "例行公文 · 规制常设"
              : mode === "kouyu"
                ? "口宣即时 · 效力稍弱 · 可能走样"
                : "会签批红 · 政令所出"}
        </span>
      </div>

      {mode === "kouyu" ? (
        <div className="space-y-3 rounded-lg border border-gold/50 bg-paper/60 p-4">
          <p className="font-kai text-sm font-bold tracking-widest text-red-dark">
            【口 宣 · 御前传谕】
          </p>
          <p className="font-kai text-xs leading-relaxed text-dim">
            口谕即时生效、不占圣旨带宽，整体效力约六成，且有走样风险。适合轻捷调度，不宜定大政。
          </p>
          <input
            type="text"
            value={kouyuTitle}
            onChange={(e) => setKouyuTitle(e.target.value)}
            placeholder="口谕事由（如：着速办和籴）"
            className="w-full rounded border border-gold/40 bg-card px-2 py-1 font-kai text-sm text-ink outline-none focus:border-red"
          />
          <textarea
            value={kouyuText}
            onChange={(e) => setKouyuText(e.target.value)}
            rows={3}
            placeholder="口谕内容……（例：着户部即日于京畿和籴粟米，毋得迟误。）"
            className="w-full resize-none rounded border border-gold/40 bg-card px-3 py-2 font-kai text-sm text-ink outline-none focus:border-red"
          />
          <div className="flex flex-wrap items-center gap-3 text-xs font-kai text-ink-light">
            <span>皇威档</span>
            <select
              value={kouyuPrestige}
              onChange={(e) => setKouyuPrestige(e.target.value)}
              className="rounded border border-gold/40 bg-card px-1.5 py-0.5 text-ink"
            >
              {["无", "微", "小", "中", "大"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <span>民情档</span>
            <select
              value={kouyuSat}
              onChange={(e) => setKouyuSat(e.target.value)}
              className="rounded border border-gold/40 bg-card px-1.5 py-0.5 text-ink"
            >
              {["无", "微", "小", "中", "大"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <span>工商征率</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={kouyuTax}
              onChange={(e) => setKouyuTax(e.target.value)}
              placeholder="留空则不动"
              className="w-24 rounded border border-gold/40 bg-card px-1.5 py-0.5 text-ink"
            />
          </div>
          <div className="flex justify-end">
            <button
              onClick={submitKouyu}
              disabled={busy || !kouyuText.trim()}
              className="flex items-center gap-1.5 rounded bg-red px-5 py-1.5 font-kai text-sm font-bold text-paper transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              传 谕
            </button>
          </div>
        </div>
      ) : mode === "free" ? (
        /* ==== 自由拟旨模式（自由打字） ==== */
        <div className="space-y-3">
          {/* 圣旨大书写区 */}
          <div className="relative rounded-lg border-2 border-gold/60 bg-gradient-to-b from-[#fefbf1] to-[#f9f2dc] p-4 shadow-paper">
            <div className="mb-2 flex items-center justify-between border-b border-gold/30 pb-1.5">
              <span className="font-kai text-sm font-bold tracking-widest text-red-dark">
                【皇帝制曰 · 御前丹诏】
              </span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="诏令标题（如：宽免二税诏）"
                className="w-48 rounded border border-gold/40 bg-card/60 px-2 py-0.5 font-kai text-xs text-ink outline-none focus:border-red"
              />
            </div>

            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              rows={5}
              placeholder="在此亲笔书写圣旨正文……（例：门下：比岁灾歉，民食维艰，朕甚悯焉。其两浙、江南诸路积欠免除二分，出内帑三万贯赈抚流民，有司敬听奉行。）"
              className="w-full resize-none bg-transparent font-kai text-[15px] leading-relaxed tracking-wide text-ink placeholder:text-dim/60 outline-none"
              autoFocus
            />

            <div className="mt-2 flex items-center justify-between border-t border-gold/20 pt-2 text-xs">
              <span className="font-kai text-dim">字数：{freeText.length} 字</span>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={minister}
                  onChange={(e) => setMinister(e.target.value)}
                  placeholder="督办重臣（默认中书省）"
                  className="w-36 rounded border border-gold/30 bg-card/60 px-2 py-0.5 font-kai text-xs text-ink outline-none"
                />
                <label className="flex cursor-pointer items-center gap-1.5 font-kai text-ink">
                  <input
                    type="checkbox"
                    checked={secret}
                    onChange={(e) => setSecret(e.target.checked)}
                    className="accent-red"
                  />
                  <span>御前密谕</span>
                </label>
              </div>
            </div>
          </div>

          {/* 典籍范例快捷填入 */}
          <div>
            <div className="mb-1.5 flex items-center gap-1 font-kai text-xs text-dim">
              <Sparkles size={12} className="text-goldDark" /> 朝廷常用诏令范本（点击速填）：
            </div>
            <div className="grid grid-cols-2 gap-2">
              {DECREE_TEMPLATES.map((tpl) => (
                <button
                  key={tpl.label}
                  onClick={() => {
                    setTitle(`${tpl.label}诏`);
                    setFreeText(tpl.text);
                  }}
                  className="rounded border border-gold/30 bg-paper/60 p-2 text-left transition hover:border-gold hover:bg-gold-light/30"
                >
                  <div className="font-kai text-xs font-bold text-red">{tpl.label}</div>
                  <div className="mt-0.5 line-clamp-1 font-kai text-[11px] text-dim">{tpl.text}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 颁布大按钮 */}
          <div className="flex justify-end pt-1">
            <button
              onClick={submitFree}
              disabled={busy || !freeText.trim()}
              className="flex items-center gap-2 rounded-lg bg-red px-8 py-2 font-kai text-base tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {busy ? "宣谕中…" : "奉天颁行"}
            </button>
          </div>
        </div>
      ) : mode === "fixed" ? (
        /* ==== 常规政务模式 ==== */
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {PROCEDURES.map((p) => (
              <button
                key={p.key}
                onClick={() => setCat(p.key)}
                className={`rounded px-2.5 py-1 font-kai text-xs transition ${
                  cat === p.key ? "bg-red text-paper shadow-sm" : "bg-paper/70 text-ink hover:bg-gold-light/40"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="space-y-2.5 rounded-lg border border-gold/40 bg-paper/60 p-3.5">
            <Field label="政务标题" value={title} onChange={setTitle} placeholder={proc.label} />
            {proc.fields.map((f) => (
              <Field
                key={f.key}
                label={f.label}
                value={valOf(f)}
                onChange={(v) => setFixedValues((s) => ({ ...s, [`${cat}.${f.key}`]: v }))}
                type={f.type}
              />
            ))}
            <Field label="督办官署" value={minister} onChange={setMinister} placeholder="有司" />
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={submitFixed}
              disabled={busy}
              className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              {busy ? "移交有司…" : "登记施行政务"}
            </button>
          </div>
        </div>
      ) : (
        /* ==== 票拟批红模式 ==== */
        <div className="space-y-3">
          {drafts.length === 0 ? (
            <p className="py-6 text-center text-dim">
              三省尚无待批诏草。可召大臣入对拟诏，或于门下省立案。
            </p>
          ) : (
            <>
              <div className="max-h-[210px] space-y-1 overflow-y-auto rounded-lg border border-gold/40 bg-paper/60 p-2.5">
                {drafts.map((d) => {
                  const id = String(d.id ?? "");
                  const sel = draftSel.has(id);
                  const src = String(d.proposer ?? d.source_minister ?? "陛下亲拟");
                  const org = String(d.org_hint ?? "政府");
                  return (
                    <label
                      key={id}
                      className="flex cursor-pointer items-center gap-2 rounded border border-transparent px-2 py-1.5 transition hover:border-gold/40 hover:bg-gold-light/20"
                    >
                      <input type="checkbox" checked={sel} onChange={() => toggleDraft(id)} className="accent-red" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-kai text-sm text-ink">{String(d.title ?? "未名诏草")}</span>
                        <span className="block text-[11px] text-dim">拟稿：{src} · 承办：{org}</span>
                      </span>
                      <button
                        onClick={(e) => { e.preventDefault(); openDetail(id); }}
                        className="shrink-0 rounded border border-gold/50 bg-card px-2 py-0.5 text-[11px] text-ink transition hover:bg-gold-light"
                      >
                        会签
                      </button>
                      <button
                        onClick={(e) => { e.preventDefault(); discardDraft(id); }}
                        disabled={polishBusy || revBusy}
                        title="弃删此诏草（不再入待签）"
                        className="shrink-0 rounded border border-red/40 bg-card px-2 py-0.5 text-[11px] text-red transition hover:bg-red/10 disabled:opacity-50"
                      >
                        弃删
                      </button>
                    </label>
                  );
                })}
              </div>

              {detailDraft && (
                <div className="rounded-lg border-2 border-gold bg-card p-3.5">
                  <p className="font-kai text-base font-bold text-red">〔{String(detailDraft.title ?? "诏草")}〕</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                    {String(detailDraft.body ?? "（正文缺）")}
                  </p>
                  <div className="mt-2 border-t border-gold/20 pt-2 text-xs text-dim">
                    <p className="font-kai">【中书省拟稿】{reviewing ? "（廷议推演中…）" : rev("memo") || "（无）"}</p>
                    <p className="mt-1 font-kai">【门下省封驳】{reviewing ? "（核议中…）" : rev("objections") || "（无）"}</p>
                    <p className="mt-1 font-kai">【尚书省六部】{reviewing ? "（承旨待办中…）" : rev("executions") || "（无）"}</p>
                    <p className="mt-1 font-kai">【会签结论】{reviewing ? "—" : rev("verdict") || "可准"}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap justify-end gap-2">
                    <button
                      onClick={() => polishDraft(String(detailDraft.id ?? ""))}
                      disabled={polishBusy || revBusy}
                      title="知制诰润色诏书全文，重入待签"
                      className="flex items-center gap-1 rounded-lg border border-gold bg-card px-5 py-1.5 font-kai text-sm text-ink transition hover:bg-gold-light disabled:opacity-60"
                    >
                      {polishBusy && <Loader2 size={14} className="animate-spin" />}
                      润色批改
                    </button>
                    <button
                      onClick={() => reviewAction("approve")}
                      disabled={revBusy}
                      className="rounded-lg bg-red px-5 py-1.5 font-kai text-sm tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
                    >
                      准奏
                    </button>
                    <button
                      onClick={rejectDraft}
                      disabled={revBusy}
                      className="rounded-lg bg-paper/60 px-5 py-1.5 font-kai text-sm text-ink transition hover:bg-gold-light disabled:opacity-60"
                    >
                      打回
                    </button>
                    <button
                      onClick={() => reviewAction("force")}
                      disabled={revBusy}
                      title="绕会签，转中旨（御笔直发）"
                      className="rounded-lg border border-gold bg-card px-5 py-1.5 font-kai text-sm text-red transition hover:bg-gold-light disabled:opacity-60"
                    >
                      御笔直发
                    </button>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between pt-1 text-xs">
                <span className="text-dim">已勾选 {draftSel.size} 道诏草</span>
                <button
                  onClick={mergeDrafts}
                  disabled={revBusy || draftSel.size < 2}
                  className="flex items-center gap-1.5 rounded-lg bg-paper/60 px-4 py-1.5 font-kai text-sm text-ink transition hover:bg-gold-light disabled:opacity-50"
                >
                  <Merge size={15} /> 汇成诏书（≥2 道）
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* 结果反馈 */}
      {result && (
        <div className="rounded-lg border border-gold/60 bg-card p-3 shadow-paper">
          <p className="whitespace-pre-wrap font-kai text-sm leading-relaxed text-ink">{result}</p>
        </div>
      )}
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, type = "text"
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "number";
}) {
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="w-24 shrink-0 font-kai text-ink-light">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded border border-gold/40 bg-card px-2.5 py-1 text-xs text-ink outline-none focus:border-red"
      />
    </label>
  );
}
