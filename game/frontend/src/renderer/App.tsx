import { useEffect, useRef } from "react";
import MapView from "./map/MapView";
import TopBar from "./hud/TopBar";
import LeftTodo from "./hud/LeftTodo";
import RightStrip from "./hud/RightStrip";
import Dock from "./hud/Dock";
import OverlayStack from "./panels/OverlayStack";
import { ApiClient, setApiClient } from "./api/client";
import { useGameStore } from "./store/gameStore";

// 单页面三层布局：L0 舆图铺底 / L1 常驻 HUD 悬浮 / L2 面板浮层栈
export default function App() {
  const setBackend = useGameStore((s) => s.setBackend);
  const setState = useGameStore((s) => s.setState);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const startShown = useRef(false);

  // 初始化：解析后端地址 → 探测已有存档，否则唤出开局面板
  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        let url = "http://127.0.0.1:8080";
        if (window.songzuo) url = await window.songzuo.getBackendUrl();
        if (cancelled) return;
        const client = new ApiClient(url);
        setApiClient(client);

        // 后端可能仍在拉起，做有限次轮询
        let health = null;
        for (let i = 0; i < 20 && !cancelled; i++) {
          try {
            health = await client.health();
            break;
          } catch {
            await new Promise((r) => setTimeout(r, 700));
          }
        }
        if (cancelled) return;
        if (!health) {
          setBackend(url, false, "后端未就绪：请确认 Python 与 backend.server 可启动");
          return;
        }
        setBackend(url, true, null);

        // 启动时必定呈现大宋游戏主菜单，由玩家选择承统开局或继续旧局
        if (!startShown.current) {
          startShown.current = true;
          pushOverlay({ kind: "newgame", title: "宋 祚 · 践 祚", dismissible: false });
        }
      } catch (e) {
        console.error("[init] 后端连接失败", e);
        if (!cancelled) setBackend("", false, String(e));
      }
    }
    init();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="paper-texture relative h-full w-full overflow-hidden bg-paper">
      {/* L0 舆图底图（取代 Tk 版 MapCanvas 的底图位） */}
      <div className="absolute inset-0">
        <MapView />
      </div>

      {/* L1 常驻 HUD */}
      <TopBar />
      <LeftTodo />
      <RightStrip />
      <Dock />

      {/* L2 面板浮层栈 */}
      <OverlayStack />
    </div>
  );
}