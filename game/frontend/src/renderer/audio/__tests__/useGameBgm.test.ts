import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useGameBgm } from "../useGameBgm";
import { audioEngine } from "../engine";

describe("useGameBgm", () => {
  beforeEach(() => {
    vi.spyOn(audioEngine, "playMusic").mockImplementation(() => {
      /* no-op */
    });
    vi.spyOn(audioEngine, "stopMusic").mockImplementation(() => {
      /* no-op */
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts BGM when entering game", () => {
    renderHook(({ inGame }) => useGameBgm(inGame), {
      initialProps: { inGame: false }
    });
    expect(audioEngine.playMusic).not.toHaveBeenCalled();
  });

  it("switches to court BGM on inGame=true", () => {
    const { rerender } = renderHook(({ inGame }) => useGameBgm(inGame), {
      initialProps: { inGame: false }
    });
    rerender({ inGame: true });
    expect(audioEngine.playMusic).toHaveBeenCalledTimes(1);
    expect(audioEngine.playMusic).toHaveBeenCalledWith("bgm_court", { loop: true, volumeBias: 0.7 });
  });

  it("stops BGM when returning to menu", () => {
    const { rerender } = renderHook(({ inGame }) => useGameBgm(inGame), {
      initialProps: { inGame: true }
    });
    rerender({ inGame: false });
    expect(audioEngine.stopMusic).toHaveBeenCalledOnce();
  });
});
