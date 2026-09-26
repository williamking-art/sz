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
  private readonly createAudioContext: () => AudioContext | null;
  private audioCtx: AudioContext | null = null;

  constructor(createAudio?: AudioFactory, createAudioContext?: () => AudioContext | null) {
    this.settings = loadAudioSettings();
    this.createAudio =
      createAudio ??
      ((src: string) => {
        const el = new Audio(src);
        // 预加载 BGM；音效按需加载即可
        el.preload = "auto";
        return el as AudioLike;
      });
    this.createAudioContext =
      createAudioContext ??
      (() => {
        const g = globalThis as unknown as {
          AudioContext?: typeof AudioContext;
          webkitAudioContext?: typeof AudioContext;
        };
        const Ctx = g.AudioContext ?? g.webkitAudioContext;
        return Ctx ? new Ctx() : null;
      });
  }

  /** 取得或创建 Web Audio 上下文（UI 点击合成音用）。 */
  private getAudioContext(): AudioContext | null {
    if (!this.audioCtx) {
      this.audioCtx = this.createAudioContext();
    }
    return this.audioCtx;
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

  /**
   * UI 点击反馈音。
   * 不依赖外部音频资源，使用 Web Audio API 合成短促三角波；
   * 在资源尚未生成时也能给玩家即时听觉反馈。
   */
  playClick(): void {
    if (this.settings.muted || this.settings.masterVolume <= 0) return;
    const ctx = this.getAudioContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(440, now + 0.08);

      const peak = Math.max(0, Math.min(1, this.effectiveVolume * 0.12));
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(peak, now + 0.005);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);

      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.1);
      // 浏览器在用户手势前会 suspend context；点击时主动 resume
      ctx.resume().catch(() => {
        /* 忽略 */
      });
    } catch {
      // 合成失败时静默降级
    }
  }
}

export const audioEngine = AudioEngine.getInstance();
