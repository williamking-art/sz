/**
 * 前端音频引擎（singleton）。
 *
 * 当前资源约定：
 * - BGM/SFX 统一从 `/audio/<key>.ogg` 加载（Vite dev / 打包后 public/audio/ 目录）。
 * - 资源尚未生成时 play() 会静默失败，不阻塞主流程。
 *
 * 设计 intentionally small：先补齐「设置持久化 + 音量/静音 + 播放接口」，
 * 后续再把触发点埋到按钮点击、事件面板、回合推进等处。
 */
import { loadAudioSettings, saveAudioSettings, type AudioSettings, DEFAULT_AUDIO_SETTINGS } from "./settings";

export type AudioCategory = "bgm" | "sfx" | "voice";

export interface PlayOptions {
  /** 是否循环（BGM 默认 true） */
  loop?: boolean;
  /** 相对主音量的档位系数，见 manifest.py AudioSlot.volume_bias */
  volumeBias?: number;
}

/** 给测试用的可观察音频元素（不暴露内部实现细节） */
export interface AudioLike {
  src: string;
  loop: boolean;
  volume: number;
  muted: boolean;
  paused: boolean;
  preload: string;
  play(): Promise<void>;
  pause(): void;
  currentTime: number;
}

type AudioFactory = (src: string) => AudioLike;

export class AudioEngine {
  /** 应用级单例 */
  private static instance: AudioEngine | null = null;
  static getInstance(): AudioEngine {
    if (!AudioEngine.instance) AudioEngine.instance = new AudioEngine();
    return AudioEngine.instance;
  }

  settings: AudioSettings;
  private currentBgm: AudioLike | null = null;
  private currentBgmKey: string | null = null;
  private readonly createAudio: AudioFactory;

  constructor(createAudio?: AudioFactory) {
    this.settings = loadAudioSettings();
    this.createAudio =
      createAudio ??
      ((src: string) => {
        const el = new Audio(src);
        // 预加载 BGM；音效按需加载即可
        el.preload = "auto";
        return el as AudioLike;
      });
  }

  private get effectiveVolume(): number {
    if (this.settings.muted) return 0;
    return this.settings.masterVolume / 100;
  }

  private applyVolume(el: AudioLike, bias = 1): void {
    el.volume = Math.max(0, Math.min(1, this.effectiveVolume * bias));
    el.muted = this.settings.muted;
  }

  setMasterVolume(vol: number): void {
    this.settings.masterVolume = Math.max(0, Math.min(100, vol));
    saveAudioSettings(this.settings);
    if (this.currentBgm) this.applyVolume(this.currentBgm);
  }

  setMuted(muted: boolean): void {
    this.settings.muted = muted;
    saveAudioSettings(this.settings);
    if (this.currentBgm) this.applyVolume(this.currentBgm);
  }

  /**
   * 播放背景音乐。重复播放同一 key 且正在播放时不重置；
   * 切换 key 时先停止旧 BGM。
   */
  playMusic(key: string, opts: PlayOptions = {}): void {
    if (this.currentBgmKey === key && this.currentBgm && !this.currentBgm.paused) {
      // 已在播放同一曲，仅刷新音量
      this.applyVolume(this.currentBgm, opts.volumeBias ?? 1);
      return;
    }
    this.stopMusic();
    const el = this.createAudio(`/audio/${key}.ogg`);
    el.loop = opts.loop ?? true;
    this.applyVolume(el, opts.volumeBias ?? 1);
    el.play().catch(() => {
      // 资源缺失、自动播放策略等情况下静默降级
    });
    this.currentBgm = el;
    this.currentBgmKey = key;
  }

  stopMusic(): void {
    if (this.currentBgm) {
      this.currentBgm.pause();
      this.currentBgm.currentTime = 0;
      this.currentBgm = null;
      this.currentBgmKey = null;
    }
  }

  /** 播放一次性音效。 */
  playSfx(key: string, opts: PlayOptions = {}): void {
    const el = this.createAudio(`/audio/${key}.ogg`);
    el.loop = false;
    this.applyVolume(el, opts.volumeBias ?? 1);
    el.play().catch(() => {
      // 静默降级
    });
  }

  /** 播放语音朗读（与 sfx 同一通道，但语义区分便于后续独立开关）。 */
  playVoice(key: string, opts: PlayOptions = {}): void {
    this.playSfx(key, { ...opts, volumeBias: opts.volumeBias ?? 0.9 });
  }
}

export const audioEngine = AudioEngine.getInstance();
