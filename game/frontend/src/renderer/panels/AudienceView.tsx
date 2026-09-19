import { useState, useRef, useEffect } from "react";
import { Loader2, X, Send, BookOpen } from "lucide-react";
import {
  getApiClient,
  type MemoryResult,
  type MemorySession,
  type MemoryDialogueRow
} from "../api/client";
import { useGameStore, pick } from "../store/gameStore";
import ministersDict from "../data/ministers_dict.json";
import MemoryDrawer, { type MemoryTab } from "./MemoryDrawer";

// 御前召对 —— 社交式会话面板（对齐用户定稿口径）：
//   · 左栏＝召对名录（会话列表：在朝大臣 + 派系领袖 + 有留档者），末条预览 + 条数；
//   · 中栏＝会话正文（消息流左右分栏、底部圣意亲裁与传谕输入框）；
//   · 右栏＝记忆库抽屉（面板顶栏「记忆库」按键开合）：会话原文/召对纪要/相关关系/
//     史略概要/变更留痕，数据源 /api/memory?minister= （只读薄壳）。
// 会话流以对话记忆库（slot_N_dialogue.db）为准：关面板再开仍能回看旧话；
// 本面板只做「读 + 触发召对」，不改动记忆库内容（无同步、无本地伪造史）。
interface DialogueTurn {
  id: string;
  speaker: string;
  isEmperor: boolean;
  timeLabel: string;
  actionNote?: string;
  content: string;
  /** 来自对话记忆库的留档消息（区别于本回合新产生的即时消息） */
  persisted?: boolean;
}

interface MinisterMeta {
  role: string;
  faction: string;
  traits: string;
  nobility: string;
  rank: string;
  in_office: boolean;
}

interface RosterEntry {
  name: string;
  role: string;
  faction: string;
}

type Dict = Record<string, unknown>;

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}
function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

export default function AudienceView({ props }: { props?: Record<string, unknown> }) {
  const popOverlay = useGameStore((s) => s.popOverlay);
  const state = useGameStore((s) => s.state);
  const setState = useGameStore((s) => s.setState);
  const ro = useGameStore((s) => s.readouts);

  const dict = ministersDict as Record<string, MinisterMeta>;
  const [current, setCurrent] = useState(String(props?.minister || "韩忠彦"));
  const currentRef = useRef(current);
  currentRef.current = current;

  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 记忆库（会话视角）：/api/memory?minister= 的只读快照 + 会话列表
  const [mem, setMem] = useState<MemoryResult | null>(null);
  const [sessions, setSessions] = useState<MemorySession[]>([]);
  const [memBusy, setMemBusy] = useState(false);
  const [memMsg, setMemMsg] = useState<string | null>(null);
  const [memOpen, setMemOpen] = useState(false);
  const [memTab, setMemTab] = useState<MemoryTab>("digest");

  const era = state
    ? `${pick<string>(state, "era_name", "建中靖国")}${pick<number>(state, "year", 1101)}年${pick<number>(state, "month", 1)}月`
    : "建中靖国元年正月";
  const stateTurn = state ? pick<number>(state, "turn", 0) : 0;

  // ---- 当前大臣的史实职衔/派系（以权威字典为准，不从列表泛化字符串推断）----
  const dictInfo = dict[current] || null;
  const currentFaction = dictInfo?.faction || "清流正论";
  const officialRank = dictInfo?.rank || "";
  const nobleTitle = dictInfo?.nobility || "";
  const isMilitary =
    /军|枢密|将|节度/.test(dictInfo?.role || "") ||
    ["西军集团", "宦官集团"].includes(currentFaction);

  function roleOf(name: string): string {
    const d = dict[name];
    if (d?.role) return d.role;
    const centralOrgs = asDict(pick(state, "central_orgs", {}));
    for (const org of Object.values(centralOrgs)) {
      const holders = asDict(asDict(org).holders);
      for (const [title, holder] of Object.entries(holders)) {
        if (asStr(holder) === name && title) return title;
      }
    }
    return String(props?.role || "朝中大臣");
  }

  const currentRole = roleOf(current);

  // ---- 会话名录：现任职事官 → 派系领袖 → 有留档者 → 当前会话（保底）----
  function buildRoster(): RosterEntry[] {
    const out: RosterEntry[] = [];
    const seen = new Set<string>();
    const push = (raw: string, role: string, faction: string) => {
      const n = (raw || "").trim();
      if (!n || seen.has(n)) return;
      seen.add(n);
      const d = dict[n];
      out.push({
        name: n,
        role: d?.role || role || "朝中大臣",
        faction: d?.faction || faction || "中枢"
      });
    };
    const centralOrgs = asDict(pick(state, "central_orgs", {}));
    for (const org of Object.values(centralOrgs)) {
      const holders = asDict(asDict(org).holders);
      for (const [title, holder] of Object.entries(holders)) push(asStr(holder), title, "中枢");
    }
    const factions = asDict(pick(state, "factions", {}));
    for (const [fn, f] of Object.entries(factions)) {
      push(asStr(asDict(f).leader), `${fn}·领袖`, fn);
    }
    for (const s of sessions) push(s.minister, "旧档在册", "在野");
    push(current, roleOf(current), currentFaction);
    return out;
  }
  const roster = buildRoster();
  const sessionMap = new Map(sessions.map((s) => [s.minister, s]));

  // ---- 立绘（无专属立绘时按文武分档兜底）----
  function portraitOf(name: string): string {
    const p = ro?.ministers?.[name]?.portrait;
    if (p) return `./portraits/${p}`;
    const r = dict[name]?.role || roleOf(name);
    return /军|枢密|将|节度/.test(r) ? "./portraits/general.png" : "./portraits/minister.png";
  }

  // ---- 属性与特质（稳定伪随机；不含忠诚——该维度为隐藏值，绝不进入 UI 文本）----
  let seed = 0;
  for (let i = 0; i < current.length; i++) seed = (seed * 37 + current.charCodeAt(i)) % 10007;
  const stats = {
    reputation: 80 + ((seed * 3) % 18),
    courage: 70 + ((seed * 7) % 25),
    military: isMilitary ? 85 + ((seed * 11) % 12) : 50 + ((seed * 11) % 25),
    govern: 82 + ((seed * 13) % 16),
    scholar: isMilitary ? 65 + ((seed * 17) % 20) : 88 + ((seed * 17) % 11)
  };

  const [turns, setTurns] = useState<DialogueTurn[]>([]);
  const [loadingSession, setLoadingSession] = useState(true);

  function greeting(name: string): DialogueTurn {
    return {
      id: `greet-${name}`,
      speaker: name,
      isEmperor: false,
      timeLabel: `${name} · ${era}`,
      actionNote: "（肃立御案前，展角幞头微垂，拱手端肃而立，目光恭慎而沉毅）",
      content: `臣【${name}】蒙陛下召对垂询，敢不竭愚竭虑，上裨圣明。今朝廷纲维初定，四方政务繁剧，陛下有何谕示，臣敬聆圣裁。`
    };
  }

  /** 记忆库留档行 → 会话气泡（含「朕」之言的左侧/右侧判定） */
  function rowToTurn(r: MemoryDialogueRow): DialogueTurn {
    const isEmperor = r.speaker === "朕";
    const when = r.turn === stateTurn ? era : `第${r.turn}回合`;
    return {
      id: `db-${r.id}`,
      speaker: isEmperor ? "皇帝陛下" : r.speaker,
      isEmperor,
      timeLabel: isEmperor ? `御批天谕 · ${when}` : `${r.speaker} · ${when}`,
      actionNote: r.stance ? `（立场：${r.stance}）` : undefined,
      content: r.text,
      persisted: true
    };
  }

  /** 拉取记忆库：resetTurns 时以留档会话流重建消息列（无留档则回落开场白） */
  async function pullMemory(name: string, resetTurns: boolean) {
    setMemBusy(true);
    setMemMsg(null);
    if (resetTurns) setLoadingSession(true);
    try {
      const res = await getApiClient().memory(name);
      setMem(res);
      setSessions(res.sessions ?? []);
      if (resetTurns) {
        const rows = res.dialogues ?? [];
        setTurns(rows.length ? rows.map(rowToTurn) : [greeting(name)]);
      }
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      setMemMsg(`记忆库读取失败：${m}`);
      if (resetTurns) setTurns([greeting(name)]);
    } finally {
      setMemBusy(false);
      setLoadingSession(false);
    }
  }

  useEffect(() => {
    void pullMemory(current, true);
    // 仅在会话对象变更时重载；state/era 只影响文案标签
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [turns, busy, loadingSession]);

  function switchTo(name: string) {
    if (name === current) return;
    setTurns([]);
    setLoadingSession(true);
    setCurrent(name);
  }

  /** 解析「发内帑 50 万 / 500000 / 五十万」→ 贯整数；失败 null。 */
  function parseInnerAmount(text: string): number | null {
    const t = text.replace(/[，,。、\s]/g, "");
    const cn: Record<string, number> = {
      零: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5,
      六: 6, 七: 7, 八: 8, 九: 9, 十: 10
    };
    const m = t.match(/(\d+(?:\.\d+)?)万/);
    if (m) return Math.round(parseFloat(m[1]) * 10000);
    const m2 = t.match(/(\d{3,})/);
    if (m2) return parseInt(m2[1], 10);
    // 五十万 / 三万
    const cnm = t.match(/([零一二两三四五六七八九十]+)万/);
    if (cnm) {
      const s = cnm[1];
      if (s === "十") return 100000;
      if (s.length === 1) return (cn[s] ?? 0) * 10000;
      if (s.length === 2 && s[0] === "十") return (10 + (cn[s[1]] ?? 0)) * 10000;
      if (s.length === 2 && s[1] === "十") return ((cn[s[0]] ?? 0) * 10) * 10000;
      if (s.length === 3 && s[1] === "十") {
        return ((cn[s[0]] ?? 0) * 10 + (cn[s[2]] ?? 0)) * 10000;
      }
    }
    return null;
  }

  const pendingTransfer = state
    ? (pick<Record<string, unknown> | null>(state, "pending_inner_transfer", null) as
        | Record<string, unknown>
        | null)
    : null;

  async function handleTransfer(approve: boolean) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await getApiClient().action(
        approve ? "confirm_inner_transfer" : "cancel_inner_transfer",
        {}
      );
      if (res.state) setState(res.state);
      setTurns((prev) => [
        ...prev,
        {
          id: `tr-${Date.now()}`,
          speaker: "朱批",
          isEmperor: true,
          timeLabel: `内帑调拨 · ${era}`,
          content: res.message || (approve ? "准，移库。" : "罢，勿庸。")
        }
      ]);
    } catch (e) {
      setTurns((prev) => [
        ...prev,
        {
          id: `tr-err-${Date.now()}`,
          speaker: current,
          isEmperor: false,
          timeLabel: `${current} · 回奏`,
          content: `调拨受阻：${e instanceof Error ? e.message : String(e)}`
        }
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(textToSend?: string) {
    const text = (textToSend || input).trim();
    if (busy || !text) return;
    const target = current; // 冻结本次召对对象：中途切换会话不得把回奏串到别人名下

    // 内帑调拨：商量确认式，不走 AI 召对（对齐 panels_govern.py）
    if (/内帑/.test(text)) {
      const amt = parseInnerAmount(text);
      if (amt === null || amt <= 0) {
        setTurns((prev) => [
          ...prev,
          {
            id: `warn-${Date.now()}`,
            speaker: "有司",
            isEmperor: false,
            timeLabel: `内帑调拨 · ${era}`,
            actionNote: "（未识金额）",
            content: "未识别金额，请注明如「发内帑 50 万入国库」。"
          }
        ]);
        if (!textToSend) setInput("");
        return;
      }
      setTurns((prev) => [
        ...prev,
        {
          id: `u-${Date.now()}`,
          speaker: "皇帝陛下",
          isEmperor: true,
          timeLabel: `御批天谕 · ${era}`,
          content: text
        }
      ]);
      if (!textToSend) setInput("");
      setBusy(true);
      try {
        const res = await getApiClient().action("propose_inner_transfer", { amount: amt });
        if (res.state) setState(res.state);
        if (currentRef.current === target) {
          setTurns((prev) => [
            ...prev,
            {
              id: `m-${Date.now()}`,
              speaker: target,
              isEmperor: false,
              timeLabel: `${target} · ${era}`,
              actionNote: "（躬身回奏，候陛下朱批）",
              content: res.message || `已谕发内帑 ${amt.toLocaleString()} 贯入国库，伏候圣裁。`
            }
          ]);
        }
      } catch (e) {
        if (currentRef.current === target) {
          setTurns((prev) => [
            ...prev,
            {
              id: `err-${Date.now()}`,
              speaker: target,
              isEmperor: false,
              timeLabel: `${target} · 调拨受阻`,
              content: `调拨受阻：${e instanceof Error ? e.message : String(e)}`
            }
          ]);
        }
      } finally {
        setBusy(false);
      }
      return;
    }

    setTurns((prev) => [
      ...prev,
      {
        id: `u-${Date.now()}`,
        speaker: "皇帝陛下",
        isEmperor: true,
        timeLabel: `御批天谕 · ${era}`,
        content: text
      }
    ]);
    if (!textToSend) setInput("");
    setBusy(true);

    try {
      const res = await getApiClient().action("audience_dialogue", {
        minister: target,
        text
      });
      if (res.state) setState(res.state);
      const aiReply = res.message || "臣敬遵温谕，必体察上意，恭谨奉行。";
      if (currentRef.current === target) {
        setTurns((prev) => [
          ...prev,
          {
            id: `m-${Date.now()}`,
            speaker: target,
            isEmperor: false,
            timeLabel: `${target} · ${era}`,
            actionNote: "（闻天语温切，躬身再拜，肃容敬答）",
            content: aiReply
          }
        ]);
      }
    } catch (e) {
      if (currentRef.current === target) {
        setTurns((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            speaker: target,
            isEmperor: false,
            timeLabel: `${target} · 传谕受阻`,
            actionNote: "（有司飞报，奏对有碍）",
            content: `奏对有阻：${e instanceof Error ? e.message : String(e)}`
          }
        ]);
      }
    } finally {
      setBusy(false);
      // 刷新侧栏与名录末条预览（不动即时消息列，避免抹掉未落库的内帑/异常提示）
      void pullMemory(target, false);
    }
  }

  // 根据大臣专业职掌分类 + 大宋当前国情态势，高度精准派生对应的圣意选项
  interface PolicyOption {
    label: string;
    badge: string;
    text: string;
    isPrimary?: boolean;
  }

  function getDynamicOptions(): PolicyOption[] {
    const opts: PolicyOption[] = [];
    const treasury = state ? pick<number>(state, "treasury", 5000000) : 5000000;
    const granary = state ? pick<number>(state, "granary", 15000000) : 15000000;
    const canalBlock = state ? pick<number>(state, "canal_block", 10) : 10;
    const external = (state as any)?.external || {};
    const liaoAtt = external["辽"]?.attitude ?? 50;
    const xixiaAtt = external["西夏"]?.attitude ?? 50;
    const activeEvents = (state as any)?.active_events || [];

    // 1. 核心定策：准奏
    opts.push({
      label: "准 奏",
      badge: "敕旨",
      text: "准卿所奏，着中书、门下及该管衙门速拟明诏颁行，毋得稽迟。",
      isPrimary: true
    });

    // 2. 根据大臣真实职权精确分类派生专业选项
    if (isMilitary || /枢密|边|帅/.test(currentRole)) {
      if (liaoAtt < 40 || xixiaAtt < 40) {
        opts.push({
          label: "九边饬备",
          badge: "戎备",
          text: "北疆辽夏塞上烽火戒严，卿总司枢府兵要，着即严饬河东、河北诸关隘坚壁清野，严防谍探。"
        });
      }
      opts.push({
        label: "点检禁厢",
        badge: "治军",
        text: "三衙禁军与各路厢军月粮饷钱可曾足额？老弱羸病者当速核定，整军经武。"
      });
      opts.push({
        label: "边贸榷场",
        badge: "互市",
        text: "辽夏近来边贸互市虚实如何？铁货茶引走私有无边吏私纵情弊？"
      });
    } else if (/相|仆射|侍郎|门下|中书/.test(currentRole)) {
      opts.push({
        label: "调停党争",
        badge: "朝局",
        text: "自建中靖国以来，朝堂新旧相攻，朋党蔓延。卿位极人臣，当如何调停众论，以安社稷？"
      });
      if (treasury < 4000000) {
        opts.push({
          label: "度支节流",
          badge: "度支",
          text: "目下国库用度日紧，三冗耗费颇巨。中书当速定裁汰冗官、省减浮费之策以充府库。"
        });
      } else {
        opts.push({
          label: "宽免积欠",
          badge: "恤民",
          text: "岁入尚安，江淮数路积年逃税包税亏欠，可议除豁免二分，以苏疲瘵。"
        });
      }
      opts.push({
        label: "整饬铨选",
        badge: "大政",
        text: "考课之法久废，请卿会同吏部严核中外荐举，务求公允。"
      });
    } else if (/户部|转运|理财/.test(currentRole)) {
      opts.push({
        label: "核查两税",
        badge: "赋税",
        text: "目下诸路夏秋两税实收与折色成数几何？隐漏逃税之田当如何稽核？"
      });
      opts.push({
        label: "平粜常平",
        badge: "仓庾",
        text: "常平太仓粮储与各路仓窖积粟足支几何？米价平籴平粜之政宜早为计。"
      });
    } else if (/御史|司谏|正言|台|谏/.test(currentRole)) {
      opts.push({
        label: "弹劾贪墨",
        badge: "风宪",
        text: "言路乃天下喉舌，近来内外百僚若有专权奸弊、贪墨渔利者，卿等自可直斥上闻。"
      });
      opts.push({
        label: "整肃言路",
        badge: "谏议",
        text: "台谏论事当秉公体国，切不可借言事攻讦异己，陷入朋党倾轧之弊。"
      });
    } else if (/工部|营造|修内司/.test(currentRole)) {
      opts.push({
        label: "督办营造",
        badge: "工役",
        text: "京畿修缮水利与军器修造工费度支如何？务使工物精纯，毋劳民伤财。"
      });
    } else {
      opts.push({
        label: "勤修厥职",
        badge: "勤政",
        text: "卿在所司宜尽心奉职，凡有关于军国利害之实务，毋得隐匿瞻顾。"
      });
    }

    // 3. 结合当前大宋宏观国情动态补充紧迫危机
    if (canalBlock >= 20) {
      opts.push({
        label: "疏浚漕纲",
        badge: "急务",
        text: "汴河淮泗漕运梗阻，江淮纲船阻滞。着发工匠民夫疏浚浅涩，按期上供太仓。"
      });
    } else if (granary < 10000000) {
      opts.push({
        label: "平抑粮价",
        badge: "仓庾",
        text: "常平仓粮储见底，京畿米价腾贵。卿当严查豪商囤积，平籴平粜以安市井。"
      });
    } else if (activeEvents.length > 0) {
      const topEv = activeEvents[0];
      const evName = topEv.title || topEv.category || "四方奏报";
      opts.push({
        label: "应对边报",
        badge: "急报",
        text: `近日地方有报【${evName}】，物议鼎沸。卿身为朝廷栋梁，可有周全应对之方？`
      });
    }

    // 4. 经典君臣情境互动
    opts.push({
      label: "赐顾渚紫笋",
      badge: "皇恩",
      text: "卿国事鞅掌，夙夜在公。内侍，特赐顾渚紫笋御茶一橐，以彰劳绩。"
    });
    opts.push({
      label: "戒骄申饬",
      badge: "戒勉",
      text: "位高权重更当谨慎自守，毋任门生亲故擅作威福，引惹言路台谏非议。"
    });

    return opts;
  }

  const dynamicOptions = getDynamicOptions();
  const digestCount = mem?.dialogue_summaries?.length ?? 0;
  const streamCount = mem?.dialogues?.length ?? 0;

  return (
    <div className="fixed inset-0 z-50 flex flex-col select-text font-kai overflow-hidden">
      {/* 1. 深度宫阙水墨背景（全屏包裹） */}
      <div
        className="absolute inset-0 bg-cover bg-center transition-all duration-700"
        style={{ backgroundImage: `url(./images/court_bg.png)` }}
      >
        <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/75 to-black/80 backdrop-blur-[2px]" />
      </div>

      {/* 2. 顶部金色端庄仪仗栏 */}
      <div className="relative z-10 flex items-center justify-between border-b border-gold/40 bg-black/50 px-6 py-2.5 backdrop-blur-sm shadow-md">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red ring-1 ring-gold shadow-md">
            <span className="font-kai text-[17px] font-bold text-[#f5ebd3]">宋</span>
          </div>
          <div>
            <h1 className="font-kai text-[18px] font-bold tracking-[0.25em] text-[#f5ebd3]">
              大 宋 垂 拱 殿 · 御 前 召 对
            </h1>
            <p className="font-kai text-[11.5px] text-gold/80 tracking-wider">
              天子亲询中枢大僚 · 言路通达 · {era}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* 记忆库入口：开合右侧记忆抽屉（会话原文/纪要/关系/史略/留痕） */}
          <button
            onClick={() => setMemOpen((v) => !v)}
            title={`记忆库 · ${current}（会话原文 ${streamCount} 条 · 纪要 ${digestCount} 篇）`}
            className={`flex items-center gap-1.5 rounded border px-3.5 py-1 text-xs font-bold transition ${
              memOpen
                ? "border-gold bg-gold/25 text-white"
                : "border-gold/40 bg-card/10 text-paper hover:border-gold hover:bg-gold/20 hover:text-white"
            }`}
          >
            <BookOpen size={15} /> 记忆库
            <span className="rounded bg-black/25 px-1 text-[10px] font-normal text-gold-light">
              {streamCount}
            </span>
          </button>
          <button
            onClick={() => popOverlay()}
            className="flex items-center gap-1.5 rounded border border-gold/40 bg-card/10 px-3.5 py-1 text-xs font-bold text-paper transition hover:border-gold hover:bg-gold/20 hover:text-white"
          >
            <X size={15} /> 退出召对
          </button>
        </div>
      </div>

      {/* 3. 三栏主舞台：会话名录（左）· 会话正文（中）· 记忆库抽屉（右，可开合） */}
      <div className="relative z-10 flex flex-1 overflow-hidden gap-3.5 px-4 pt-2.5 pb-3.5">
        {/* 左栏：召对名录（会话列表）+ 当前大臣名片 */}
        <div className="flex w-[272px] shrink-0 flex-col overflow-hidden rounded-[4px] border border-gold/50 bg-black/45 backdrop-blur-sm shadow-xl">
          {/* 当前大臣名片（立绘小像 + 官品/爵位双轨） */}
          <div className="flex items-center gap-2.5 border-b border-gold/40 px-3 py-2.5">
            <img
              src={portraitOf(current)}
              alt={current}
              className="h-14 w-14 shrink-0 rounded border border-gold/50 bg-black/40 object-cover object-top"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-kai text-[16px] font-bold tracking-widest text-[#f5ebd3]">
                {current}
              </p>
              <p className="truncate text-[11px] text-gold/80">{currentRole}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {officialRank && (
                  <span className="rounded border border-gold/60 bg-black/70 px-1.5 py-0.5 text-[10px] font-bold text-gold">
                    {officialRank}
                  </span>
                )}
                {nobleTitle && (
                  <span className="rounded border border-red/60 bg-red-950/70 px-1.5 py-0.5 text-[10px] font-bold text-[#f2d3a0]">
                    {nobleTitle}
                  </span>
                )}
                {!officialRank && !nobleTitle && (
                  <span className="rounded border border-border/60 bg-black/60 px-1.5 py-0.5 text-[10px] font-bold text-[#c9bda0]">
                    白身布衣
                  </span>
                )}
                <span className="rounded border border-gold/40 bg-black/50 px-1.5 py-0.5 text-[10px] text-[#c9bda0]">
                  {currentFaction}
                </span>
              </div>
            </div>
          </div>

          {/* 五维属性（不含忠诚——隐藏值不进 UI） */}
          <div className="grid grid-cols-5 gap-1 border-b border-gold/40 px-2.5 py-1.5 text-center">
            {[
              ["清誉", stats.reputation],
              ["胆识", stats.courage],
              ["武略", stats.military],
              ["理政", stats.govern],
              ["学识", stats.scholar]
            ].map(([k, v]) => (
              <div key={String(k)} className="rounded border border-gold/25 bg-black/30 py-0.5">
                <p className="text-[9.5px] text-gold/60">{k}</p>
                <p className="font-kai text-[12.5px] font-bold text-[#f5ebd3]">{v}</p>
              </div>
            ))}
          </div>

          {/* 会话列表 */}
          <div className="flex items-center justify-between px-3 pt-2 pb-1">
            <span className="text-[10.5px] tracking-widest text-gold/70">召 对 名 录</span>
            <span className="text-[10px] text-gold/50">{roster.length} 位</span>
          </div>
          <div className="flex-1 overflow-y-auto pb-2">
            {roster.map((r) => {
              const active = r.name === current;
              const s = sessionMap.get(r.name);
              return (
                <button
                  key={r.name}
                  onClick={() => switchTo(r.name)}
                  disabled={busy}
                  className={`flex w-full items-start gap-2.5 border-l-2 px-3 py-2 text-left transition disabled:opacity-60 ${
                    active
                      ? "border-gold bg-gold/20"
                      : "border-transparent hover:bg-white/5"
                  }`}
                >
                  <img
                    src={portraitOf(r.name)}
                    alt=""
                    className="h-9 w-9 shrink-0 rounded border border-gold/40 bg-black/40 object-cover object-top"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[13px] font-bold text-[#f5ebd3]">
                        {r.name}
                      </span>
                      {s && (
                        <span className="shrink-0 text-[9.5px] text-gold/70">
                          第{s.last_turn}回合 · {s.count}条
                        </span>
                      )}
                    </div>
                    <p className="truncate text-[10.5px] text-gold/70">{r.role}</p>
                    <p className="truncate text-[10.5px] text-[#c9bda0]">
                      {s ? `${s.last_speaker === "朕" ? "朕" : s.last_speaker}：${s.last_text}` : "尚无召对留档"}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* 中栏：会话正文 */}
        <div className="flex min-w-0 flex-1 flex-col rounded-[4px] border border-gold/60 bg-[#f9f5ea]/95 shadow-2xl overflow-hidden h-full">
          {/* 会话题头 */}
          <div className="flex items-center justify-between border-b border-gold/40 bg-[#f4ebd6] px-4 py-2">
            <div className="min-w-0">
              <p className="truncate font-kai text-[15px] font-bold tracking-widest text-ink">
                垂拱殿召对 · {current}
              </p>
              <p className="truncate text-[11px] text-dim">
                {currentRole} · {currentFaction} · {era}
              </p>
            </div>
            <span className="shrink-0 text-[11px] text-dim">
              留档 {turns.filter((t) => t.persisted).length} 条
            </span>
          </div>

          {/* 消息流 */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
            {loadingSession && turns.length === 0 && (
              <div className="flex items-center gap-2 py-2 text-xs text-dim">
                <Loader2 size={14} className="animate-spin text-goldDark" />
                <span>正在调阅 {current} 的旧档…</span>
              </div>
            )}

            {turns.map((t) => (
              <div
                key={t.id}
                className={`flex flex-col animate-card-in ${t.isEmperor ? "items-end" : "items-start"}`}
              >
                {/* 说话人与时节 */}
                <div className="flex items-center gap-2 mb-1 text-[11.5px] text-dim px-1">
                  <span className="font-bold">{t.timeLabel}</span>
                  {t.persisted && (
                    <span className="rounded bg-gold/15 px-1 text-[9.5px] text-goldDark">留档</span>
                  )}
                </div>

                {/* 动作细节描写（灰色宋体斜体） */}
                {t.actionNote && (
                  <div className="max-w-[85%] text-[12px] italic text-dim/90 mb-1.5 px-2 leading-relaxed">
                    {t.actionNote}
                  </div>
                )}

                {/* 对话正文 */}
                <div
                  className={`relative max-w-[88%] rounded-lg p-3.5 shadow-sm text-[14.5px] leading-relaxed border ${
                    t.isEmperor
                      ? "border-red/40 bg-red/10 text-red-dark font-medium"
                      : "border-gold/40 bg-card text-ink font-normal"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{t.content}</p>
                </div>
              </div>
            ))}

            {busy && (
              <div className="flex items-center gap-2 text-dim text-xs py-2 px-1">
                <Loader2 size={14} className="animate-spin text-goldDark" />
                <span>{current} 深思谋定，正拟奏对草疏中…</span>
              </div>
            )}
          </div>

          {/* 底部圣意交互区 */}
          <div className="border-t border-gold/40 bg-[#f4ebd6] p-3 space-y-2.5">
            {/* 上层：基于大宋当前局势与大臣职权动态派生的决策命令标签条 */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[12px] font-bold text-red-dark mr-1">圣意亲裁：</span>
              {dynamicOptions.map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => handleSend(opt.text)}
                  disabled={busy}
                  title={opt.text}
                  className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-bold transition shadow-sm disabled:opacity-50 ${
                    opt.isPrimary
                      ? "bg-red text-paper hover:bg-red-dark"
                      : "border border-gold/60 bg-paper text-ink hover:bg-gold-light hover:border-gold hover:text-red"
                  }`}
                >
                  <span
                    className={`text-[9.5px] px-1 py-0.2 rounded font-sans ${
                      opt.isPrimary ? "bg-black/20 text-gold-light" : "bg-gold/15 text-goldDark"
                    }`}
                  >
                    {opt.badge}
                  </span>
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>

            {/* 内帑调拨待准栏（对齐 Tk pending_bar） */}
            {pendingTransfer && (
              <div className="mb-2 flex items-center gap-2 rounded border border-gold/60 bg-gold-light/30 px-3 py-1.5">
                <span className="font-kai text-sm text-amber-800">
                  已谕：发内帑 {Number(pendingTransfer.amount || 0).toLocaleString()} 贯入国库，待准
                </span>
                <button
                  onClick={() => handleTransfer(true)}
                  disabled={busy}
                  className="ml-auto rounded bg-red px-3 py-0.5 font-kai text-xs font-bold text-paper hover:bg-red-dark disabled:opacity-50"
                >
                  准
                </button>
                <button
                  onClick={() => handleTransfer(false)}
                  disabled={busy}
                  className="rounded border border-gold/60 bg-paper px-3 py-0.5 font-kai text-xs text-ink hover:bg-gold-light disabled:opacity-50"
                >
                  罢
                </button>
              </div>
            )}

            {/* 下层：长条宣纸传旨输入框 */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={busy}
                placeholder={`向 ${current} 传达圣意口谕（例：卿身为朝廷柱石，有何经略之策？直接敲 Enter 发送）`}
                className="flex-1 rounded border border-gold/60 bg-card px-3.5 py-2 text-[14px] text-ink outline-none focus:border-red shadow-inner placeholder:text-dim/60"
              />
              <button
                onClick={() => handleSend()}
                disabled={busy || !input.trim()}
                className="flex items-center gap-1.5 rounded bg-red px-5 py-2 text-sm font-bold tracking-widest text-paper shadow-card hover:bg-red-dark transition disabled:opacity-50"
              >
                {busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                传 谕
              </button>
            </div>
          </div>
        </div>

        {/* 右栏：记忆库（嵌入本面板的功能，顶栏按键开合） */}
        {memOpen && (
          <MemoryDrawer
            minister={current}
            data={mem}
            busy={memBusy}
            msg={memMsg}
            tab={memTab}
            onTab={setMemTab}
            onClose={() => setMemOpen(false)}
            onRefresh={() => void pullMemory(current, false)}
          />
        )}
      </div>
    </div>
  );
}
