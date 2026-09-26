import { useEffect } from "react";
import { audioEngine } from "./engine";

/**
 * 根据是否处于游戏内自动切换 BGM。
 * - 进入舆图：播放朝堂雅乐 `bgm_court`
 * - 回到主菜单：停止 BGM
 */
export function useGameBgm(inGame: boolean): void {
  useEffect(() => {
    if (inGame) {
      audioEngine.playMusic("bgm_court", { loop: true, volumeBias: 0.7 });
    } else {
      audioEngine.stopMusic();
    }
  }, [inGame]);
}
