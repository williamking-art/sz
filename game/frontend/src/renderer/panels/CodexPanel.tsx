import { useState, useMemo } from "react";
import { Search, BookOpen, ExternalLink } from "lucide-react";
import codexData from "../data/codex.json";

interface CodexItem {
  key: string;
  name: string;
  sub: string;
  desc: string;
  fields: [string, string][];
  links: [string, string, string][]; // [cat, key, label]
}

type CategoryKey = "building" | "minister" | "org" | "tech" | "branch" | "region" | "mechanism" | "event";

const CATEGORIES: { key: CategoryKey; label: string }[] = [
  { key: "minister", label: "名臣" },
  { key: "org", label: "官制" },
  { key: "region", label: "地理" },
  { key: "tech", label: "科技" },
  { key: "branch", label: "兵种" },
  { key: "building", label: "营造" },
  { key: "mechanism", label: "典章" },
  { key: "event", label: "大事" },
];

export default function CodexPanel({ props }: { props?: { category?: string; entry?: string } }) {
  const initialCat = (props?.category as CategoryKey) || "minister";
  const [activeCat, setActiveCat] = useState<CategoryKey>(initialCat);
  const [query, setQuery] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(props?.entry || null);

  // 当前分类下的辞条列表
  const rawItems = (codexData[activeCat] || []) as CodexItem[];

  // 搜索过滤
  const filteredItems = useMemo(() => {
    if (!query.trim()) return rawItems;
    const q = query.trim().toLowerCase();
    return rawItems.filter(
      (it) =>
        it.name.toLowerCase().includes(q) ||
        it.sub.toLowerCase().includes(q) ||
        it.desc.toLowerCase().includes(q) ||
        it.fields.some(([k, v]) => k.includes(q) || v.toLowerCase().includes(q))
    );
  }, [rawItems, query]);

  // 当前选中的辞条
  const activeItem = useMemo(() => {
    if (selectedKey) {
      const hit = rawItems.find((it) => it.key === selectedKey);
      if (hit) return hit;
    }
    return filteredItems[0] || null;
  }, [selectedKey, rawItems, filteredItems]);

  function handleJump(targetCat: string, targetKey: string) {
    if (CATEGORIES.some((c) => c.key === targetCat)) {
      setActiveCat(targetCat as CategoryKey);
      setSelectedKey(targetKey);
      setQuery("");
    }
  }

  return (
    <div className="flex h-[520px] flex-col gap-3">
      {/* 顶部：分类 Tab + 检索框 */}
      <div className="flex items-center justify-between gap-3 border-b border-gold/40 pb-2.5">
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              onClick={() => {
                setActiveCat(c.key);
                setSelectedKey(null);
              }}
              className={`rounded px-2.5 py-1 font-kai text-sm transition ${
                activeCat === c.key
                  ? "bg-red text-paper shadow-sm"
                  : "bg-paper/70 text-ink hover:bg-gold-light/40"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* 搜索框 */}
        <div className="relative flex items-center">
          <Search size={14} className="absolute left-2.5 text-ink-light" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索典籍..."
            className="w-36 rounded border border-gold/40 bg-card py-1 pl-7 pr-2.5 font-sans text-xs text-ink outline-none transition focus:border-red focus:w-44"
          />
        </div>
      </div>

      {/* 主体：左侧目录 + 右侧古籍详注 */}
      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* 左：条目目录 */}
        <div className="flex w-52 flex-col gap-1 overflow-y-auto pr-1">
          {filteredItems.length === 0 ? (
            <div className="py-8 text-center font-kai text-xs text-dim">无匹配典籍辞条</div>
          ) : (
            filteredItems.map((item) => {
              const isSelected = activeItem?.key === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setSelectedKey(item.key)}
                  className={`group flex items-center justify-between rounded border px-2.5 py-1.5 text-left transition ${
                    isSelected
                      ? "border-red/60 bg-red/10 text-red-dark shadow-sm"
                      : "border-gold/30 bg-paper/50 text-ink hover:border-gold hover:bg-paper"
                  }`}
                >
                  <span className="font-kai text-sm font-medium tracking-wide truncate">
                    {item.name}
                  </span>
                  {item.sub && (
                    <span
                      className={`ml-1 shrink-0 rounded px-1 py-0.2 text-[10px] ${
                        isSelected ? "bg-red/20 text-red" : "bg-card text-dim"
                      }`}
                    >
                      {item.sub}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        {/* 右：辞条祥卡 */}
        <div className="flex flex-1 flex-col overflow-y-auto rounded-lg border border-gold/50 bg-paper/70 p-4 shadow-paper">
          {activeItem ? (
            <div className="space-y-3.5">
              {/* 标题与类别 */}
              <div className="flex items-center justify-between border-b border-gold/30 pb-2">
                <div className="flex items-baseline gap-2">
                  <span className="font-kai text-xl font-bold tracking-widest text-ink">
                    {activeItem.name}
                  </span>
                  {activeItem.sub && (
                    <span className="font-kai text-xs text-goldDark">〔{activeItem.sub}〕</span>
                  )}
                </div>
                <BookOpen size={16} className="text-goldDark/70" />
              </div>

              {/* 属性表格 */}
              {activeItem.fields && activeItem.fields.length > 0 && (
                <div className="rounded border border-gold/30 bg-card/60 p-2.5">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    {activeItem.fields.map(([k, v]) => (
                      <div key={k} className="flex justify-between border-b border-border/40 py-0.5">
                        <span className="text-ink-light">{k}</span>
                        <span className="font-medium text-ink truncate max-w-[140px]" title={v}>
                          {v}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 列传详述 / 历史典制 */}
              {activeItem.desc && (
                <div className="space-y-1">
                  <div className="font-kai text-xs font-bold text-red-dark">【事迹与志注】</div>
                  <p className="font-kai text-[13px] leading-relaxed text-ink/90 whitespace-pre-line text-justify bg-card/40 rounded p-2.5 border border-border/30">
                    {activeItem.desc}
                  </p>
                </div>
              )}

              {/* 关联条目跳转 */}
              {activeItem.links && activeItem.links.length > 0 && (
                <div className="pt-1">
                  <div className="mb-1.5 font-kai text-xs text-dim">关联典籍：</div>
                  <div className="flex flex-wrap gap-1.5">
                    {activeItem.links.map(([cat, key, label]) => (
                      <button
                        key={key}
                        onClick={() => handleJump(cat, key)}
                        className="flex items-center gap-1 rounded border border-gold/50 bg-paper px-2 py-0.5 font-kai text-xs text-ink transition hover:border-red hover:text-red"
                      >
                        <ExternalLink size={10} /> {label}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-full items-center justify-center font-kai text-sm text-dim">
              请在左侧选择典籍辞条查阅
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
