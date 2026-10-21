import { Compass } from "lucide-react";
import { useGameStore, hudEra } from "../store/gameStore";

/** 地图题签：让全屏地图拥有自己的标题与纪年，不占用地图交互。 */
export default function MapCartouche() {
  const state = useGameStore((s) => s.state);
  const era = hudEra(state);

  return (
    <div className="sz-map-cartouche pointer-events-none absolute left-1/2 top-4 z-[18] hidden -translate-x-1/2 items-center gap-3 px-5 py-2 xl:flex" aria-label="大宋天下舆图">
      <span className="sz-cartouche-rule" />
      <Compass size={17} strokeWidth={1.4} className="text-[#8f6e28]" aria-hidden="true" />
      <div className="text-center">
        <p className="font-brush text-[14px] font-bold tracking-[.42em] text-[#2b1d12]">大 宋 天 下</p>
        <p className="mt-0.5 font-kai text-[9px] tracking-[.2em] text-[#76664a]">{era || "建中靖国元年正月"} · 舆图</p>
      </div>
      <Compass size={17} strokeWidth={1.4} className="rotate-180 text-[#8f6e28]" aria-hidden="true" />
      <span className="sz-cartouche-rule" />
    </div>
  );
}
