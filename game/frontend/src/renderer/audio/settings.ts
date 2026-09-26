/**
 * 音频偏好持久化。
 * 与 AudioEngine 解耦，方便测试与 SSR/非浏览器环境降级。
 */

export interface AudioSettings {
  /** 主音量 0~100 */
  masterVolume: number;
  /** 全局静音 */
  muted: boolean;
}

export const DEFAULT_AUDIO_SETTINGS: AudioSettings = {
  masterVolume: 75,
  muted: false
};

const STORAGE_KEY = "songzuo:audio";

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Number.isFinite(n) ? n : min));
}

export function loadAudioSettings(): AudioSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AudioSettings>;
      return {
        masterVolume: clamp(Number(parsed.masterVolume ?? DEFAULT_AUDIO_SETTINGS.masterVolume), 0, 100),
        muted: Boolean(parsed.muted)
      };
    }
  } catch {
    // localStorage 不可用或 JSON 损坏时回落默认值
  }
  return { ...DEFAULT_AUDIO_SETTINGS };
}

export function saveAudioSettings(s: AudioSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // 隐私模式/存储满时静默失败
  }
}
