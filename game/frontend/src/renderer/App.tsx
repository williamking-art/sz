import { useEffect, useRef } from "react";
import MapView from "./map/MapView";
import TopBar from "./hud/TopBar";
import LeftTodo from "./hud/LeftTodo";
import RightStrip from "./hud/RightStrip";
import Dock from "./hud/Dock";
import OverlayStack from "./panels/OverlayStack";
import MainMenu from "./main-menu/MainMenu";
import { ApiClient, setApiClient } from "./api/client";
import { useGameStore, pick } from "./store/gameStore";

// 单页面三层布局：L0 舆图铺底 / L1 常驻 HUD 悬浮 / L2 面板浮层栈
export default function App() {
  const setBackend = useGameStore((s) => s.setBackend);
  const setState = useGameStore((s) => s.setState);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const inGame = useGameStore((s) => s.inGame);
  const state = useGameStore((s) => s.state);
  const overlays = useGameStore((s) => s.overlays);
  const startShown = useRef(false);
  // 终局浮层守卫：game_over 置真后只自动弹一次；game_over 复位（新开局）后再遇终局可再弹
  const concludeShownRef = useRef(false);

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

        // 默认进入 MainMenu 全屏开屏大作主菜单
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

  // 终局自动入口：后端 game_over == true（推演/诏令/事件结算后随 state 快照下发）时
  // 自动唤起「终局评估」浮层（ConcludePanel 挂载时自行 client.conclude() 拉取评估数据）。
  // ref 守卫保证同一局只弹一次；关闭（pop）后不再自动重弹，直至重开新局 game_over 复位。
  const gameOver = state ? pick<boolean>(state, "game_over", false) : false;
  useEffect(() => {
    // 离开游戏回主菜单（或尚未开局）时复位守卫：下次载入/重开仍可自动弹一次
    if (!inGame) {
      concludeShownRef.current = false;
      return;
    }
    if (!gameOver) {
      concludeShownRef.current = false;
      return;
    }
    if (concludeShownRef.current) return;
    if (overlays.some((o) => o.kind === "conclude")) return;
    concludeShownRef.current = true;
    pushOverlay({ kind: "conclude", title: "终局评估" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameOver, inGame, overlays, pushOverlay]);

  // 未进入游戏时：全屏呈现史诗级大宋开屏主界面 (MainMenu)
  if (!inGame) {
    return (
      <div className="relative h-full w-full overflow-hidden bg-black">
        <MainMenu />
        {/* 主菜单上支持唤起典籍库与机务设置 */}
        <OverlayStack />
      </div>
    );
  }

  // 进入游戏后：呈现大宋天下舆图与常驻 HUD 治国中枢
  return (
    <div className="paper-texture relative h-full w-full overflow-hidden bg-paper">
      {/* L0 舆图底图 */}
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