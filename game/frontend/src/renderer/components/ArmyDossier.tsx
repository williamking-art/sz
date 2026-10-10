import { X } from "lucide-react";
import type { ArmyUnitReadout } from "../api/client";
import { wan } from "../utils/format";
import constants from "../data/constants.json";

// 单军档案（诸军明细）—— **多入口共用的唯一实现**。
//
// 为什么要抽出来：地图驻军卡、州路档案「军政」页、全军面板三处都要"点开某一支军看"，
// 若各写一份，同一支部队会因字段/格式化漂移在不同入口显示不同结论（口径分叉）。
// 故此处是**唯一**单军档案组件：调用方只传 `unit`（/api/readouts::army 的行）。
//
// 纪律（承 AGENTS.md §3 / panels/README §纪律）：
//   ① **只呈现**：所有数值来自后端读数，前端不重算粮饷/战力；
//   ② **缺失 ≠ 0**：`monthly_pay` 等为 null/undefined 时显示「未定义」，**不得**显示 0
//      （0 会被读成"这支军不花钱"）；
//   ③ 装备键名取导出面 `constants.equip_keys`，不复制字面量。

type Dict = Record<string, unknown>;

const EQUIP_KEY_NAMES = (constants.equip_keys ?? []) as string[];
const EQUIP_UNITS: Record<string, string> = {
  枪刀: "件", 弓弩: "件", 火器: "件", 战马: "匹", 盔甲: "件", 舟船: "艘", 器械: "件"
};
const EQUIP_KEYS: [string, string][] = EQUIP_KEY_NAMES.map(
  (k) => [k, EQUIP_UNITS[k] ?? "件"] as [string, string]
);

function asDict(v: unknown): Dict {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : {};
}

/** 有限数 → number；缺失/非有限 → null（**不回落 0**）。 */
function numOrNull(v: unknown): number | null {
  const n = Number(v);
  return v === null || v === undefined || !Number.isFinite(n) ? null : n;
}

/** 缺失呈现：统一「未定义」，不用空白或 0 冒充。 */
function Undefined() {
  return <span className="text-xs italic text-dim">未定义</span>;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5">
      <dt className="shrink-0 text-dim">{label}</dt>
      <dd className="min-w-0 text-right text-ink">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-3">
      <p className="font-kai text-sm font-bold tracking-[0.2em] text-red">{title}</p>
      <div className="mt-1">{children}</div>
    </section>
  );
}

export interface ArmyDossierProps {
  unit: ArmyUnitReadout | null;
  onClose: () => void;
}

export default function ArmyDossier({ unit, onClose }: ArmyDossierProps) {
  if (!unit) return null;
  const u = unit as unknown as Dict;
  const troops = numOrNull(u.troops);
  const morale = numOrNull(u.morale);
  const training = numOrNull(u.training);
  const equipRate = numOrNull(u.equip_rate);
  const monthlyPay = numOrNull(u.monthly_pay);
  const monthlyGrain = numOrNull(u.monthly_grain);
  const arrears = numOrNull(u.arrears);

  const branches = Object.entries(asDict(u.branches))
    .map(([b, n]) => [b, numOrNull(n) ?? 0] as [string, number])
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  const branchSum = branches.reduce((a, [, n]) => a + n, 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={"军伍档案 " + String(u.name ?? "")}
      onClick={onClose}
    >
      <div
        className="sz-panel max-h-[86dvh] w-[min(560px,94vw)] overflow-auto p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline justify-between gap-3 border-b border-border pb-2">
          <div className="min-w-0">
            <p className="sz-overlay-kicker">军伍档案</p>
            <p className="truncate font-kai text-lg font-bold text-ink">{String(u.name ?? "—")}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="shrink-0 rounded p-1 text-ink-light transition hover:bg-gold-light hover:text-ink"
          >
            <X size={18} />
          </button>
        </div>

        <p className="mt-1.5 text-xs text-dim">
          {String(u.tier || "未定义")}　{String(u.army_name || "未定义")}　
          {String(u.org_arm || "未定义")}　{String(u.scale || "")}
          {u.serial ? "第" + String(u.serial) : ""}
        </p>

        <Section title="编 制 与 驻 地">
          <dl className="text-sm">
            <Row label="驻 地">{String(u.station || "未定义")}</Row>
            <Row label="防 区">{String(u.defense_line || "未定义")}</Row>
            <Row label="统 帅">{String(u.commander || "未定义")}</Row>
            <Row label="总 兵 额">
              {troops === null ? <Undefined /> : <span>{wan(troops, "人")}</span>}
            </Row>
          </dl>
        </Section>

        <Section title="兵 种 构 成">
          {branches.length === 0 ? (
            <Undefined />
          ) : (
            <ul className="text-sm">
              {branches.map(([b, n]) => (
                <li key={b} className="flex justify-between gap-3 py-0.5">
                  <span className="text-ink">{b}</span>
                  <span className="text-ink">{n.toLocaleString()}人</span>
                </li>
              ))}
              {troops !== null && branchSum !== troops ? (
                <li className="pt-1 text-xs text-dim">
                  兵种合计 {branchSum.toLocaleString()} 人 与 总兵额 {troops.toLocaleString()} 人不一致
                </li>
              ) : null}
            </ul>
          )}
        </Section>

        <Section title="粮 饷 与 消 耗">
          <dl className="text-sm">
            <Row label="月 军 饷">
              {monthlyPay === null ? <Undefined /> : <span>{wan(monthlyPay, "贯")}</span>}
            </Row>
            <Row label="月 粮 消 耗">
              {monthlyGrain === null ? <Undefined /> : <span>{wan(monthlyGrain, "石")}</span>}
            </Row>
            <Row label="累 计 欠 饷">
              {arrears === null ? (
                <Undefined />
              ) : (
                <span className={arrears > 0 ? "font-bold text-red" : undefined}>
                  {wan(arrears, "贯")}
                </span>
              )}
            </Row>
          </dl>
        </Section>

        <Section title="战 力 状 态">
          <dl className="text-sm">
            <Row label="士 气">{morale === null ? <Undefined /> : <span>{Math.round(morale)}</span>}</Row>
            <Row label="训 练 度">{training === null ? <Undefined /> : <span>{Math.round(training)}</span>}</Row>
            <Row label="装 备 配 给">
              {equipRate === null ? <Undefined /> : <span>{Math.round(equipRate * 100)}%</span>}
            </Row>
          </dl>
        </Section>

        <Section title="装 备 明 细">
          <ul className="text-sm">
            {EQUIP_KEYS.map(([k, unitSuffix]) => {
              const v = numOrNull(asDict(u.equip)[k]);
              return (
                <li key={k} className="flex justify-between gap-3 py-0.5">
                  <span className="text-ink">{k}</span>
                  <span className="text-ink">{v === null ? <Undefined /> : wan(v, unitSuffix)}</span>
                </li>
              );
            })}
          </ul>
        </Section>
      </div>
    </div>
  );
}
