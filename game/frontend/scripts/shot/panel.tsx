// 宋祚 · 面板截图台（**dev-only**，不进产品构建）
// 用法：npm run shot:build → 起静态服务 → 无头浏览器访问
//   ?panel=localarchive&route=两浙路[&kind=circuit|city]
//   ?panel=provincemilitary&route=两浙路
// 目的：让"只看得到代码、看不到界面"这件事有解——真渲染 + 真 Tailwind + 真组件，出 PNG 供人/代理目视。
import { createRoot } from "react-dom/client";
import "../../src/renderer/styles/theme.css";
import LocalArchivePanel from "../../src/renderer/panels/LocalArchivePanel";
import ProvinceMilitaryPanel from "../../src/renderer/panels/ProvinceMilitaryPanel";

const q = new URLSearchParams(location.search);
const panel = q.get("panel") ?? "localarchive";
const name = q.get("route") ?? "两浙路";
const kind = q.get("kind") ?? "circuit";
const width = Number(q.get("w") ?? 920);

const node = document.getElementById("root")!;
createRoot(node).render(
  <div className="min-h-screen bg-paper p-5" style={{ width }}>
    <div className="mb-3 font-kai text-[12px] text-dim">
      截图台（dev-only）· panel={panel} · route={name} · kind={kind}
    </div>
    {panel === "provincemilitary"
      ? <ProvinceMilitaryPanel props={{ route: name }} />
      : <LocalArchivePanel props={{ kind, name }} />}
  </div>
);
