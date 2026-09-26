import { describe, it, expect, beforeEach, vi } from "vitest";
import { AudioEngine, type AudioLike, audioEngine } from "../engine";
import { loadAudioSettings, saveAudioSettings, DEFAULT_AUDIO_SETTINGS } from "../settings";

interface MockCtx {
  factory: () => Record<string, unknown>;
  resume: ReturnType<typeof vi.fn>;
  createOscillator: ReturnType<typeof vi.fn>;
  createGain: ReturnType<typeof vi.fn>;
  oscillator: Record<string, unknown>;
  gain: Record<string, unknown>;
}

function mockAudioContext(): MockCtx {
  const resume = vi.fn().mockResolvedValue(undefined);
  const oscillator = {
    type: "",
    frequency: { value: 0, setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    disconnect: vi.fn()
  };
  const gain = {
    gain: {
      value: 0,
      setValueAtTime: vi.fn(),
      linearRampToValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn()
    },
    connect: vi.fn(),
    disconnect: vi.fn()
  };
  const createOscillator = vi.fn(() => oscillator);
  const createGain = vi.fn(() => gain);
  const factory = () => ({
    resume,
    currentTime: 0,
    createOscillator,
    createGain,
    destination: {}
  });
  return { factory, resume, createOscillator, createGain, oscillator, gain };
}

function mockAudio(): { instances: AudioLike[]; factory: (src: string) => AudioLike } {
  const instances: AudioLike[] = [];
  const factory = (src: string): AudioLike => {
    const el = {
      src,
      loop: false,
      volume: 1,
      muted: false,
      paused: true,
      preload: "auto",
      currentTime: 0,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(() => {
        el.paused = true;
      })
    };
    instances.push(el);
    return el;
  };
  return { instances, factory };
}

describe("audio settings persistence", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns defaults when localStorage empty", () => {
    expect(loadAudioSettings()).toEqual(DEFAULT_AUDIO_SETTINGS);
  });

  it("persists and reloads custom settings", () => {
    saveAudioSettings({ masterVolume: 42, muted: true });
    expect(loadAudioSettings()).toEqual({ masterVolume: 42, muted: true });
  });

  it("clamps out-of-range volume", () => {
    saveAudioSettings({ masterVolume: 200, muted: false });
    expect(loadAudioSettings().masterVolume).toBe(100);
    saveAudioSettings({ masterVolume: -10, muted: false });
    expect(loadAudioSettings().masterVolume).toBe(0);
  });
});

describe("AudioEngine", () => {
  beforeEach(() => {
    localStorage.clear();
    audioEngine.stopMusic();
    audioEngine.setMasterVolume(DEFAULT_AUDIO_SETTINGS.masterVolume);
    audioEngine.setMuted(DEFAULT_AUDIO_SETTINGS.muted);
  });

  it("loads persisted settings on construction", () => {
    saveAudioSettings({ masterVolume: 33, muted: true });
    const { factory } = mockAudio();
    const engine = new AudioEngine(factory);
    expect(engine.settings).toEqual({ masterVolume: 33, muted: true });
  });

  it("applies volume and muted to BGM", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.setMasterVolume(50);
    engine.playMusic("bgm_court");
    expect(instances).toHaveLength(1);
    expect(instances[0].src).toBe("/audio/bgm_court.ogg");
    expect(instances[0].loop).toBe(true);
    expect(instances[0].volume).toBe(0.5);
    expect(instances[0].muted).toBe(false);
    expect(instances[0].play).toHaveBeenCalledOnce();
  });

  it("does not restart same BGM if already playing", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.playMusic("bgm_court");
    instances[0].paused = false;
    engine.playMusic("bgm_court");
    expect(instances).toHaveLength(1);
    expect(instances[0].play).toHaveBeenCalledOnce();
  });

  it("switches BGM when key changes", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.playMusic("bgm_court");
    engine.playMusic("bgm_battle");
    expect(instances).toHaveLength(2);
    expect(instances[0].pause).toHaveBeenCalledOnce();
    expect(instances[1].src).toBe("/audio/bgm_battle.ogg");
  });

  it("applies volume bias to SFX", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.setMasterVolume(100);
    engine.playSfx("sfx_click", { volumeBias: 0.6 });
    expect(instances[0].volume).toBe(0.6);
    expect(instances[0].loop).toBe(false);
  });

  it("silences all output when muted", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.setMasterVolume(100);
    engine.setMuted(true);
    engine.playSfx("sfx_click");
    expect(instances[0].muted).toBe(true);
    expect(instances[0].volume).toBe(0);
  });

  it("updates current BGM volume when master volume changes", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.setMasterVolume(100);
    engine.playMusic("bgm_court");
    engine.setMasterVolume(25);
    expect(instances[0].volume).toBe(0.25);
  });

  it("stops and resets BGM", () => {
    const { instances, factory } = mockAudio();
    const engine = new AudioEngine(factory);
    engine.playMusic("bgm_court");
    engine.stopMusic();
    expect(instances[0].pause).toHaveBeenCalledOnce();
    expect(instances[0].currentTime).toBe(0);
  });

  it("handles play() rejection gracefully", () => {
    const factory = (src: string): AudioLike => {
      const el = {
        src,
        loop: false,
        volume: 1,
        muted: false,
        paused: true,
        preload: "auto",
        currentTime: 0,
        play: vi.fn().mockRejectedValue(new Error("autoplay blocked")),
        pause: vi.fn()
      };
      return el;
    };
    const engine = new AudioEngine(factory);
    expect(() => engine.playSfx("missing")).not.toThrow();
  });

  it("synthesizes a UI click via Web Audio API", () => {
    const { factory: ctxFactory, createOscillator, createGain, oscillator, gain, resume } = mockAudioContext();
    const ctxFactorySpy = vi.fn(ctxFactory);
    const { factory } = mockAudio();
    const engine = new AudioEngine(factory, ctxFactorySpy as unknown as () => AudioContext);
    engine.setMasterVolume(100);
    engine.setMuted(false);
    engine.playClick();
    expect(ctxFactorySpy).toHaveBeenCalledTimes(1);
    expect(createOscillator).toHaveBeenCalledTimes(1);
    expect(createGain).toHaveBeenCalledTimes(1);
    expect(oscillator.start).toHaveBeenCalledTimes(1);
    expect(oscillator.stop).toHaveBeenCalledTimes(1);
    expect(resume).toHaveBeenCalledTimes(1);
    // 峰值音量 = effectiveVolume * 0.12 = 0.12
    expect(
      (gain.gain as { linearRampToValueAtTime: ReturnType<typeof vi.fn> }).linearRampToValueAtTime
    ).toHaveBeenCalledWith(expect.closeTo(0.12, 4), expect.closeTo(0.005, 4));
  });

  it("does not synthesize click when muted", () => {
    const { factory: ctxFactory, createOscillator } = mockAudioContext();
    const { factory } = mockAudio();
    const engine = new AudioEngine(factory, ctxFactory as unknown as () => AudioContext);
    engine.setMuted(true);
    engine.playClick();
    expect(createOscillator).not.toHaveBeenCalled();
  });

  it("scales click volume with master volume", () => {
    const { factory: ctxFactory, gain } = mockAudioContext();
    const { factory } = mockAudio();
    const engine = new AudioEngine(factory, ctxFactory as unknown as () => AudioContext);
    engine.setMasterVolume(50);
    engine.setMuted(false);
    engine.playClick();
    // effectiveVolume=0.5, peak=0.5*0.12=0.06
    expect((gain.gain as { linearRampToValueAtTime: ReturnType<typeof vi.fn> }).linearRampToValueAtTime).toHaveBeenCalledWith(
      expect.closeTo(0.06, 4),
      expect.closeTo(0.005, 4)
    );
  });
});
